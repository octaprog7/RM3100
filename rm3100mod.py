"""MicroPython module for RM3100 Geomagnetic Sensor"""
import micropython

# MicroPython
# mail: goctaprog@gmail.com
# MIT license
from time import sleep_ms
from micropython import const
# from collections import namedtuple

from sensor_pack_2.bus_service import I2cAdapter
from sensor_pack_2.geosensmod import (MagnetometerData, UpdateRates, OversampleLevels,
                                      PerformanceProfiles, MagRange, DataStatus,
                                      ICommonMagnitometer, AXIS_X, AXIS_Y, AXIS_Z, AXIS_ALL)
from sensor_pack_2.base_sensor import IDentifier, DeviceEx, check_value, bytes_to_int


# минимальное время, которое необходимо внутреннему АЦП датчика для выполнения полного цикла измерений.
_BASE_CONV_TIME_ADC_US = const(1667)
# 0x00C8 — это значение по умолчанию для регистров Cycle Count (счетчика циклов) по осям X, Y и Z.
_DEFAULT_CYCLE_COUNT = const(0x00C8)
_UPDATE_RATE_OFFSET = const(0x92)
# =========================================================================
# Адреса регистров RM3100 (MagI2C Register Map)
# =========================================================================
# Регистры управления режимами измерений
_REG_ADDR_POLL = const(0x00)      # Polls for a Single Measurement (Однократный замер)
_REG_ADDR_CMM = const(0x01)       # Initiates Continuous Measurement Mode (Непрерывный замер)

# Регистры счетчика циклов (Cycle Count Registers)
# Запись 2 байт (MSB, LSB) начинается с этих адресов
_REG_ADDR_CCX = const(0x04)       # Cycle Count Register – X Axis (MSB)
_REG_ADDR_CCY = const(0x06)       # Cycle Count Register – Y Axis (MSB)
_REG_ADDR_CCZ = const(0x08)       # Cycle Count Register – Z Axis (MSB)

# Регистр частоты обновления (Time Between Readings)
_REG_ADDR_TMRC = const(0x0B)      # Sets Continuous Measurement Mode Data Rate

# Регистры результатов измерений (Measurement Results)
# Чтение 3 байт (MSB, MID, LSB) начинается с этих адресов
_REG_ADDR_MX = const(0x24)        # Measurement Results – X Axis (MSB)
_REG_ADDR_MY = const(0x27)        # Measurement Results – Y Axis (MSB)
_REG_ADDR_MZ = const(0x2A)        # Measurement Results – Z Axis (MSB)

# Регистры диагностики, статуса и служебные
_REG_ADDR_BIST = const(0x33)      # Built-In Self Test (Самопроверка)
_REG_ADDR_STATUS = const(0x34)    # Status of DRDY (Готовность данных)
_REG_ADDR_HSHAKE = const(0x35)    # Handshake Register (Управление сбросом DRDY)
_REG_ADDR_REVID = const(0x36)     # MagI2C Revision Identification (ID ревизии чипа)

# Кортеж адресов регистров Cycle Count (MSB) для осей X, Y, Z.
# Индексация: 0 -> X, 1 -> Y, 2 -> Z
_CC_REGISTERS = const((_REG_ADDR_CCX, _REG_ADDR_CCY, _REG_ADDR_CCZ))

# Маппинг аппаратных индексов TMRC (0..13) в период обновления данных (мс).
# Значения рассчитаны как 1/ODR и округлены до целых для удобства использования с sleep_ms().
# Согласно Table 5-4 даташита RM3100.
_TMRC_PERIOD = const((
    2,     # 0: 600 Hz  -> ~1.67 мс
    3,     # 1: 300 Hz  -> ~3.33 мс
    7,     # 2: 150 Hz  -> ~6.67 мс
    13,    # 3: 75 Hz   -> ~13.33 мс
    27,    # 4: 37 Hz   -> ~27.03 мс
    56,    # 5: 18 Hz   -> ~55.56 мс
    111,   # 6: 9 Hz    -> ~111.11 мс
    222,   # 7: 4.5 Hz  -> ~222.22 мс
    435,   # 8: 2.3 Hz  -> ~434.78 мс
    833,   # 9: 1.2 Hz  -> ~833.33 мс
    _BASE_CONV_TIME_ADC_US,  # 10: 0.6 Hz -> ~1666.67 мс
    3333,  # 11: 0.3 Hz -> ~3333.33 мс
    6667,  # 12: 0.15 Hz-> ~6666.67 мс
    13333  # 13: 0.075Hz-> ~13333.33 мс
))

# Маппинг унифицированных индексов UpdateRates (0..10) в индексы TMRC (0..13) для RM3100.
_UPDATE_RATE_TO_TMRC = const((
    6,   # 0: HZ_10   -> TMRC 6  (~9 Гц)
    4,   # 1: HZ_50   -> TMRC 4  (~37 Гц, заводской default 0x96)
    2,   # 2: HZ_100  -> TMRC 2  (~150 Гц)
    1,   # 3: HZ_200  -> TMRC 1  (~300 Гц)
    0,   # 4: HZ_500  -> TMRC 0  (~600 Гц, аппаратный максимум RM3100)
    0,   # 5: HZ_1000 -> TMRC 0  (~600 Гц, fallback на максимум)
    10,  # 6: HZ_0_5  -> TMRC 10 (~0.6 Гц)
    5,   # 7: HZ_20   -> TMRC 5  (~18 Гц)
    9,   # 8: HZ_1    -> TMRC 9  (~1.2 Гц)
    1,   # 9: HZ_300  -> TMRC 1  (~300 Гц, точное совпадение!)
    0,   # 10: HZ_400 -> TMRC 0  (~600 Гц, ближайший поддерживаемый сверху)
))

# Маппинг индексов PerformanceProfiles (0..4) в пары (UpdateRate, OversampleLevel).
_PROFILE_TO_SETTINGS = (
    # 0: HIGH_ACCURACY (Стационарный компас: макс. точность, разумная скорость)
    # HZ_10 = ~9 Hz, CC=400 = минимальный шум
    (UpdateRates.HZ_10, OversampleLevels.ULTRA_HIGH),

    # 1: BACKGROUND_MONITORING (Экономия энергии: низкая частота, мин. циклы)
    # HZ_1 = ~1.2 Hz, CC=30 = минимальное потребление
    (UpdateRates.HZ_1, OversampleLevels.HIGH_SPEED),

    # 2: DYNAMIC_NAVIGATION (Мобильные роботы: баланс скорости и точности)
    # HZ_50 = ~37 Hz, CC=100 = хороший баланс
    (UpdateRates.HZ_50, OversampleLevels.BALANCED),

    # 3: TILT_COMPENSATION (С акселерометром: высокая частота для синхронизации)
    # HZ_100 = ~150 Hz, CC=100 = высокая скорость сбора
    (UpdateRates.HZ_100, OversampleLevels.BALANCED),

    # 4: FAST_RESPONSE (Следящие механизмы: макс. скорость отклика)
    # HZ_300 = ~300 Hz, CC=30 = максимальная скорость
    (UpdateRates.HZ_300, OversampleLevels.HIGH_SPEED),
)

# карта унифицированных индексов OversampleLevels (0..5) в значения Cycle Count для RM3100.
# По Table 3-1 даташита, полезный диапазон CC: 30..400.
_OVERSAMPLE_TO_CC = (
    400,  # 0: ULTRA_HIGH  -> 400 (максимальное разрешение, мин. шум)
    200,  # 1: HIGH        -> 200 (заводской default, отличный баланс)
    150,  # 2: MEDIUM_HIGH -> 150
    100,  # 3: BALANCED    -> 100 (хорошая скорость при приемлемом шуме)
    50,   # 4: MEDIUM_LOW  -> 50  (высокая скорость, повышенный шум)
    30,   # 5: HIGH_SPEED  -> 30  (минимально допустимое значение без квантования)
)

# Допустимый диапазон значений Cycle Count для RM3100 (согласно Table 3-1 даташита)
_CC_MIN = const(30)
_CC_MAX = const(400)

@micropython.native
def _check_cycle_count(value: int):
    """Проверяет, что значение Cycle Count находится в допустимом диапазоне 30..400."""
    check_value(value, range(_CC_MIN, _CC_MAX + 1),
                f"Invalid Cycle Count: {value}. Допустимый диапазон: {_CC_MIN}..{_CC_MAX}")

def _get_multiplier(cycle_count: int) -> float:
    """Возвращает множитель для перевода сырых данных АЦП (LSB) в Гауссы (G)."""
    # Дополнительная страховка: если вдруг пришло некорректное значение,
    # приводим его к безопасному диапазону или кидаем ошибку
    _check_cycle_count(cycle_count)

    # Формула: Multiplier = 0.01 (G/µT) / (Cycle_Count * 0.375)
    return 0.01 / (cycle_count * 0.375)


class RM3100(ICommonMagnitometer, IDentifier):
    """RM3100 Geomagnetic Sensor."""

    def __init__(self, adapter: I2cAdapter, address: int = 0x20):
        # адрес в диапазоне 0x20..0x23!
        check_value(address, range(0x20, 0x24), f"Invalid address value: {address}")
        self._connection = DeviceEx(adapter=adapter, address=address, big_byte_order=True)
        #
        self._buf_2 = bytearray(2)  # для хранения
        self._buf_3 = bytearray(3)  # для хранения
        self._buf_9 = bytearray(9)  # для хранения
        # =========================================================================
        # СОСТОЯНИЕ ДАТЧИКА (для start_measurement без параметров)
        # =========================================================================
        # если Истина, то get_measurement_value возвращает результат в безразмерных (сырых значениях)
        # если Ложь, то get_measurement_value возвращает результат в Гауссах!
        self._raw_mode = False
        self._axis = AXIS_ALL  # По умолчанию измеряю все 3 оси (0b111 = 7)
        self._single_mode = True  # По умолчанию Force State (однократный замер)
        self._full_meas_seq = True  # По умолчанию DRDY после завершения ВСЕХ осей
        self._update_rate_index = 0  # устанавливается в методе setup()
        self._over_sample_index = 0 # устанавливается в методе setup()

        # Профиль производительности является "главным".
        # Он автоматически определит правильные _update_rate_index и _over_sample_index.
        self._performance_profile = PerformanceProfiles.TILT_COMPENSATION
        # =========================================================================
        # Кэш множителя. Вычисляю через _get_multiplier для CC=200 (заводской default).
        # Это значение будет перезаписано в setup() -> set_performance_profile() -> set_oversample_index(),
        self._multiplier = _get_multiplier(_DEFAULT_CYCLE_COUNT)
        self.setup()
        # self.refresh_config()

    def _read_reg(self, reg_addr: int, bytes_count: int = 1) -> bytes:
        """Считывает значение из регистра по адресу регистра 0..0x10. Смотри _get_reg_address"""
        return self._connection.read_reg(reg_addr, bytes_count)

    def read_buf_from_mem(self, mem_addr: int, buf: bytearray):
        """Читает из устройства с адресом address в буфер buf, начиная с адреса в устройстве mem_addr.
        Количество считываемых байт определяется длинной буфера buf."""
        return self._connection.read_buf_from_mem(mem_addr, buf)  # 16 bit value (int16)

    def _write_reg(self, reg_addr: int, value: int, bytes_count: int = 1):
        """Записывает в регистр с адресом reg_addr значение value по шине."""
        self._connection.write_reg(reg_addr, value, bytes_count)

    def set_update_rate_index(self, index: int | None = None) -> int:
        """Устанавливает и возвращает индекс частоты обновления данных (ODR).
        Преобразует универсальный индекс UpdateRates в аппаратный индекс TMRC для RM3100."""
        if index is not None:
            check_value(index, range(len(_UPDATE_RATE_TO_TMRC)), f"Invalid update rate index: {index}")
            tmrc_index = _UPDATE_RATE_TO_TMRC[index]
            # Запись
            self._write_reg(_REG_ADDR_TMRC, _UPDATE_RATE_OFFSET + tmrc_index)
            # Сохраняю для внутреннего состояния
            self._update_rate_index = index

        return self._update_rate_index

    def _get_cmm(self) -> int:
        """Возвращает значение регистра CMM"""
        return self._read_reg(_REG_ADDR_CMM)[0]

    def set_raw_mode(self, value: bool | None = None) -> bool:
        """Устанавливает тип значения, возвращаемого методом get_measurement_value.
        Если value Истина, то get_measurement_value возвращает сырые безразмерные значения.
        Если value Ложь, то get_measurement_value возвращает значения в Гаусс.
        Значение используется методом start_measurement!
        Возвращает текущее значение типа значения, возвращаемого методом get_measurement_value.
        """
        if value is None:
            return self._raw_mode
        self._raw_mode = value
        return value

    def get_id(self):
        """Возвращает значение (REVID), которое не определено в документации, что странно!
        return MagI2C Revision Identification"""
        return self._read_reg(_REG_ADDR_REVID)[0]

    def is_continuously_mode(self):
        """Возвращает Истина, когда включен режим периодических измерений!"""
        return 0 != (0x01 & self._get_cmm())

    def is_single_shot_mode(self):
        """Возвращает Истина, когда включен режим однократных измерений (по запросу)!
        Для переопределения программистом!!!"""
        return 0 == (0x01 & self._get_cmm())

    def get_data_status(self, raw: bool = True) -> int | DataStatus:
        """Возвращает кортеж битов(номер бита): DRDY(7), """
        stat = self._read_reg(_REG_ADDR_STATUS)[0]
        if raw:
            return stat
        return DataStatus(DataReady= (0 != (stat & 0x80)), Saturated=None, DataLost=None)

    def is_data_ready(self) -> bool:
        return bool(0x80 & self.get_data_status())

    def perform_self_test(self) -> bool:
        """Возвращает кортеж результатов самопроверки!"""
        wr = self._write_reg
        try:
            wr(reg_addr=_REG_ADDR_CMM, value=0x00)
            wr(reg_addr=_REG_ADDR_HSHAKE, value=0x08)

            wr(_REG_ADDR_BIST, 0x8F)      # start the built-in self test
            wr(_REG_ADDR_POLL, 0x70)  # запускаю измерение по всем трем осям
            counter = 0
            while True:
                sleep_ms(10)
                if counter > 3 or self.is_data_ready():
                    break   # The end of the built-in self test sequence
                counter += 1
            bist = self._read_reg(_REG_ADDR_BIST)[0]
            z_axis_ok = 0 != bist & 0x40
            y_axis_ok = 0 != bist & 0x20
            x_axis_ok = 0 != bist & 0x10
            timeout_period = bool((bist & 0b1100) >> 2)
            lr_periods = bool(bist & 0b11)
            return z_axis_ok and y_axis_ok and x_axis_ok and timeout_period and lr_periods
        finally:
            wr(reg_addr=_REG_ADDR_BIST, value=0x00)  # disable self-test mode, clear STE bit
            wr(reg_addr=_REG_ADDR_HSHAKE, value=0x0A)

    def soft_reset(self):
        """
        Выполняет программный сброс датчика к заводским настройкам.
        Поскольку у RM3100 нет аппаратного бита сброса, мы вручную
        записываем значения по умолчанию и синхронизируем состояние.
        """
        # Останавливаю любые текущие измерения
        self._write_reg(_REG_ADDR_CMM, 0x00)

        # Сбрасываю TMRC на заводской default (0x96 -> ~37 Гц)
        self._write_reg(_REG_ADDR_TMRC, 0x96)

        # Сбрасываю Cycle Count на заводской default (0x00C8 = 200)
        # 2 байта!
        self._connection.write_reg(_REG_ADDR_CCX, _DEFAULT_CYCLE_COUNT, 2)
        self._connection.write_reg(_REG_ADDR_CCY, _DEFAULT_CYCLE_COUNT, 2)
        self._connection.write_reg(_REG_ADDR_CCZ, _DEFAULT_CYCLE_COUNT, 2)

        # Сбрасываю HSHAKE на безопасное значение (DRC0=0, DRC1=1)
        self._write_reg(_REG_ADDR_HSHAKE, 0x0A)

        # Синхронизирую программное состояние с тем, что мы только что записали
        self.refresh_config()


    def start_measurement(self):
        """Запускает измерение, используя текущие настройки, сохраненные в переменных экземпляра.

        Настройки предварительно изменяются через методы:
        - set_measurement_axis(axis_mask) или прямое присваивание self._axis
        - set_continuous_mode(value)
        - set_update_rate_index(index)

        Для RM3100 оси кодируются в битах 4-6 регистров POLL и CMM.
        Поскольку AXIS_X=1, AXIS_Y=2, AXIS_Z=4, сдвиг на 4 бита влево (<< 4)
        дает правильные битовые позиции: 0x10, 0x20, 0x40.
        """
        # Сдвигаю битовую маску осей в правильную позицию для регистров RM3100
        # Пример: AXIS_ALL (7) << 4 = 0x70 (измерение по всем трем осям)
        axis_mask = self._axis << 4

        # Режим DRDY: 0 = ждать завершения ВСЕХ запрошенных осей, 1 = ждать ЛЮБУЮ одну ось
        drdm = 0 if self._full_meas_seq else 1

        if not self._single_mode:
            # =====================================================================
            # Continuous Measurement Mode (CMM)
            # =====================================================================
            # Устанавливаю частоту обновления.
            # Вызываю метод
            self.set_update_rate_index(self._update_rate_index)

            # Формирую значение для регистра CMM (0x01):
            # Бит 0 (START)      = 1 (запуск непрерывного режима)
            # Бит 2 (DRDM)       = drdm (условие срабатывания флага готовности)
            # Биты 4-6 (CMX/Y/Z) = axis_mask (выбранные оси)
            cmm_value = axis_mask | (drdm << 2) | 0x01
            self._write_reg(_REG_ADDR_CMM, value=cmm_value)
            return

        # =====================================================================
        # Single Measurement Mode (POLL / Force State)
        # =====================================================================
        # Сначала отключаю Continuous Mode!
        self._write_reg(_REG_ADDR_CMM, value=0x00)

        # Запускаю однократное измерение (биты 4-6 = axis_mask)
        self._write_reg(_REG_ADDR_POLL, value=axis_mask)

    def set_axis_cycle_count(self, axis: int, value: int):
        """Устанавливает количество циклов для измерения магнитного поля по указанной оси.
        :param axis: Битовая маска оси (AXIS_X, AXIS_Y или AXIS_Z).
        :param value: Количество циклов (допустимый диапазон: 30..400)."""
        check_value(axis, (AXIS_X, AXIS_Y, AXIS_Z), f"Invalid axis: {axis}")
        _check_cycle_count(value)
        # Получаю адрес регистра
        addr = _CC_REGISTERS[axis >> 1]
        # Упаковка и запись 16-битного значения (Big-Endian)
        # bo_t = self._connection._get_byteorder_as_str()  # ">H"
        # bts = struct.pack(bo_t[1] + "H", value)
        self._connection.write_reg(addr, value, 2)

    def get_axis_cycle_count(self, axis: int) -> int:
        """
        Возвращает количество циклов для измерения магнитного поля по указанной оси.
        :param axis: Битовая маска оси (AXIS_X, AXIS_Y или AXIS_Z).
        :return: Текущее значение Cycle Count (int).
        """
        check_value(axis, (AXIS_X, AXIS_Y, AXIS_Z), f"Invalid axis: {axis}")

        # Получаю адрес регистра
        addr = _CC_REGISTERS[axis >> 1]

        # 2 байта в int
        self.read_buf_from_mem(addr, self._buf_2)
        return bytes_to_int(source=self._buf_2, big_byte_order=True, signed=False)

    def set_oversample_index(self, index: int | None = None) -> int:
        """Устанавливает или возвращает индекс уровня передискретизации (OSR).
        Для RM3100 это транслируется в значение Cycle Count для всех трех осей."""
        if index is not None:
            # Проверка границ (допустимы индексы от 0 до 5, как в OversampleLevels)
            check_value(index, range(len(_OVERSAMPLE_TO_CC)), f"Invalid oversample index: {index}")
            # Получаю целевое значение Cycle Count из константы
            target_cc = _OVERSAMPLE_TO_CC[index]
            # Применяю это значение ко всем трем осям через наш внутренний метод
            self.set_axis_cycle_count(AXIS_X, target_cc)
            self.set_axis_cycle_count(AXIS_Y, target_cc)
            self.set_axis_cycle_count(AXIS_Z, target_cc)
            # запоминаю множитель
            self._multiplier = _get_multiplier(target_cc)
            # Сохраняю индекс для внутреннего состояния (если понадобится)
            self._over_sample_index = index

        return self._over_sample_index

    def _get_all_meas_result(self) -> tuple:
        """Для наибыстрейшего считывания за один вызов всех результатов измерений из датчика по
        относительно медленной шине!"""
        bts = self._buf_9
        self.read_buf_from_mem(_REG_ADDR_MX, bts)
        t = (bytes_to_int(source=bts[3 * index:3 * (index+1)], big_byte_order=True, signed=True) for index in range(3))
        return tuple(t)

    def setup(self):
        """Настройка режима работы датчика.
            active_pwr_mode - если Истина, то датчик включен, иначе в состоянии stand by.
            data_rate - частота измерений (0..3) при периодических(!) измерениях.
            single_mode - если Истина, то каждое измерение нужно запускать вызовом start_measure,
                            иначе измерения запускаются автоматически с частотой data_rate
        """
        # DRC0 = 0, DRC1 = 1
        self._write_reg(reg_addr=_REG_ADDR_HSHAKE, value=0x0A)
        # Применяю профиль. Этот метод сам вызовет set_update_rate_index
        # и set_oversample_index с правильными значениями для TILT_COMPENSATION.
        self.set_performance_profile(self._performance_profile)

    def __next__(self) -> None | MagnetometerData:
        """возвращает результат только в режиме периодических измерений!"""
        if self.is_continuously_mode() and self.is_data_ready():
            return self.get_measurement_value(AXIS_ALL)
        return None

    def get_measurement_value(self, axis: int = AXIS_ALL) -> MagnetometerData:
        """
        Возвращает значения магнитного поля.
        Если self._raw_mode == True, возвращает сырые отсчеты АЦП (float).
        Если self._raw_mode == False, возвращает значения в Гауссах (G),
        используя единый множитель для всех осей.
        Примечание: параметр axis сохранен для совместимости с интерфейсом IMagnetometer,
        но физически всегда читаются все 3 оси за одну транзакцию I2C для максимальной скорости!
        """
        raw_x, raw_y, raw_z = self._get_all_meas_result()

        # Если запрошен режим "сырых" данных, возвращаем их как есть
        if self._raw_mode:
            return MagnetometerData(x=float(raw_x), y=float(raw_y), z=float(raw_z), is_raw=True)

        # Режим Гауссов: читаю Cycle Count (значение одинаково для X, Y, Z)
        # cc = self.get_axis_cycle_count(AXIS_X)

        # self._multiplier был вычислен сначала в __инит__ затем в set_oversample_index!
        _mul = self._multiplier
        # один множитель ко всем осям
        return MagnetometerData(
            x=raw_x * _mul,
            y=raw_y * _mul,
            z=raw_z * _mul,
            is_raw=False
        )

    def set_continuous_mode(self, value: bool | None = None) -> bool:
        """Устанавливает или возвращает режим непрерывных измерений."""
        if value is not None:
            self._single_mode = not value
        return not self._single_mode

    def set_magnitude_range_index(self, range_idx: int | None = None) -> int:
        """Устанавливает или возвращает индекс диапазона измерений.
        RM3100 имеет фиксированный аппаратный диапазон ±800 мкТл (±8 G)."""
        if range_idx is not None:
            # можно добавить предупреждение, если пытаются установить не G8
            if range_idx != MagRange.G8:
                pass
        # Всегда возвращаю G8, так как это единственный физический диапазон RM3100
        return MagRange.G8

    def set_performance_profile(self, profile: int | None = None) -> int:
        """Устанавливает или возвращает профиль производительности.
        Для RM3100 профиль транслируется в конкретные значения ODR и Cycle Count."""
        if profile is not None:
            # Проверка границ
            check_value(profile, range(len(_PROFILE_TO_SETTINGS)), f"Invalid performance profile: {profile}")
            # распаковка пары настроек из константы по индексу
            ur_idx, os_idx = _PROFILE_TO_SETTINGS[profile]
            # Применяю настройки
            self.set_update_rate_index(ur_idx)
            self.set_oversample_index(os_idx)
            # Сохраняю текущий профиль
            self._performance_profile = profile

        # Возвращаю текущий профиль (или переданный, если он еще не был сохранен)
        return self._performance_profile

    def refresh_config(self):
        """Считывает текущие настройки из регистров датчика и синхронизирует их
        с внутренним программным состоянием.
        Важно вызывать после soft_reset()."""
        # Читаю регистр CMM (0x01) для определения режима измерений
        cmm = self._get_cmm()

        # Бит 0 (START): 1 = Continuous Mode, 0 = Single/POLL Mode
        self._single_mode = not bool(cmm & 0x01)

        # Бит 2 (DRDM): 0 = ждать завершения ВСЕХ запрошенных осей, 1 = ждать ЛЮБУЮ одну
        self._full_meas_seq = not bool(cmm & 0x04)

        # Биты 4, 5, 6 (CMX, CMY, CMZ): Извлекаю маску осей (0..7)
        self._axis = (cmm >> 4) & 0x07

        # Fallback: если ни одна ось не выбрана (0x00), считаю, что выбраны все
        if self._axis == 0:
            self._axis = AXIS_ALL

        # Читаю регистр TMRC (0x0B) для определения частоты обновления
        tmrc_val = self._read_reg(_REG_ADDR_TMRC)[0]
        tmrc_index = tmrc_val - _UPDATE_RATE_OFFSET  # 0x92 = 146. tmrc_val - 146

        # Обратный поиск индекса в кортеже
        try:
            self._update_rate_index = _UPDATE_RATE_TO_TMRC.index(tmrc_index)
        except ValueError:
            # Если значение не найдено (например, был записан мусор),
            # fallback на заводской default (~37 Гц), который соответствует HZ_50
            self._update_rate_index = UpdateRates.HZ_50

        # Читаю регистр Cycle Count (по оси X, так как обычно они настроены одинаково)
        cc_val = self.get_axis_cycle_count(AXIS_X)

        # Обратный поиск индекса в кортеже OversampleLevels
        try:
            self._over_sample_index = _OVERSAMPLE_TO_CC.index(cc_val)
        except ValueError:
            # Fallback на заводской default (CC=200), который соответствует HIGH
            self._over_sample_index = OversampleLevels.HIGH

        # Синхронизирую кэш множителя на основе восстановленного Cycle Count
        target_cc = _OVERSAMPLE_TO_CC[self._over_sample_index]
        self._multiplier = _get_multiplier(target_cc)

    def get_conversion_cycle_time(self) -> int:
        """Возвращает период обновления данных (1/ODR) в МИЛЛИСЕКУНДАХ
        для текущих настроек датчика.

        Используется для расчета задержек в цикле опроса:
        time.sleep_ms(sensor.get_conversion_cycle_time())

        :return: Период между измерениями в миллисекундах (int)."""
        # Получаем аппаратный индекс TMRC из текущего унифицированного индекса
        tmrc_index = _UPDATE_RATE_TO_TMRC[self._update_rate_index]

        # Возвращаем период из _TMRC_PERIOD
        return _TMRC_PERIOD[tmrc_index]

    # НОВЫЙ метод
    def get_adc_conversion_time(self) -> int:
        """Возвращает чистое время работы АЦП в МИКРОСЕКУНДАХ (мкс).
        Согласно даташиту RM3100: 1667 мкс * (2 ^ TMRC_index)."""
        tmrc_index = _UPDATE_RATE_TO_TMRC[self._update_rate_index]
        return _BASE_CONV_TIME_ADC_US * (1 << tmrc_index)