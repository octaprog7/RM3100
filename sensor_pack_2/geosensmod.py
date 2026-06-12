"""Типы и вспомогательный код для интегральных магнитометров.
Магнитометры выдают значения в собственной трехмерной декартовой системе координат (x, y, z)."""
import math
import json
import micropython
from micropython import const
from collections import namedtuple

from sensor_pack_2.base_sensor import IBaseSensorEx, Iterator

# Магнитометры практически всегда выдают значения в собственной трехмерной декартовой системе координат (x, y, z).
# Поле is_raw: bool Истина, когда поля кортежа содержат сырые(безразмерные) данные!
MagnetometerData = namedtuple("MagnetometerData", "x y z is_raw")
# Имена составляющих напряженности вектора магнитного поля в [Тесла]/[Гаусс]
Mag_Axis_Names = ('_', 'x', 'y', '_', 'z')
# Битовые маски осей (для флагов и комбинаций)
AXIS_X = const(1)  # 0b001
AXIS_Y = const(2)  # 0b010
AXIS_Z = const(4)  # 0b100
AXIS_ALL = const(AXIS_X | AXIS_Y | AXIS_Z)  # 0b111 = 7


# Универсальный(!) формат статуса для всех(!) магнитометров
# DataReady: новые данные доступны для чтения
# Saturated: сенсор насыщен (превышен диапазон измерений)
# DataLost: данные потеряны (переполнение буфера или ошибка)
DataStatus = namedtuple("DataStatus", "DataReady Saturated DataLost")


class MagRange:
    """Диапазоны измерений магнитного поля (в Гауссах, G).
    Используется как пространство имен для методов set_range_index."""
    G2 = const(0)  # ±2 G (высокая точность, QMC5883L)
    G8 = const(1)  # ±8 G (стандарт, QMC5883L, RM3100)
    G30 = const(2)  # ±30 G (широкий диапазон, MMC5603NJ)


class UpdateRates:
    """Унифицированные индексы частоты обновления данных (ODR) для магнитометров.
    Конкретный драйвер транслирует этот индекс в ближайший поддерживаемый
    аппаратный режим данного чипа."""
    HZ_10 = const(0)  # 10 Гц; компас, минимум шума
    HZ_50 = const(1)  # 50 Гц; для робототехники
    HZ_100 = const(2)  # 100 Гц; для динамичных систем
    HZ_200 = const(3)  # 200 Гц; высокая скорость для QMC/MMC, ~150-300 Гц для RM3100
    HZ_500 = const(4)  # 500 Гц; только для MMC5603 и RM3100, QMC выдаст ошибку или максимум
    HZ_1000 = const(5)  # 1000 Гц; только для MMC5603. В спец. режиме, RM3100 выдаст максимум
    # для HSCDTD008A
    HZ_0_5 = const(6)
    HZ_20 = const(7)
    # для RM3100
    HZ_1 = const(8)  # 1 Гц; очень низкое энергопотребление
    HZ_300 = const(9)  # 300 Гц; нативная частота для RM3100
    HZ_400 = const(10)  # 400 Гц; высокая скорость для RM3100


class OversampleLevels:
    """Уровни компромисса "Точность vs Скорость" для магнитометров.
    Расширенный набор для поддержки высоких разрешений RM3100 и MMC5603NJ.
    ГЛАВНОЕ(!):
    - Чем выше уровень точности, тем ниже максимальная частота опроса (ODR) и выше время измерения.
    - Чем выше уровень скорости, тем выше шум и ниже разрешение."""
    ULTRA_HIGH = const(0)  # Макс. точность, мин. шум (QMC: 512, MMC: BW=00, RM3100: CC=400)
    HIGH = const(1)  # Высокая точность (QMC: 256, MMC: BW=01, RM3100: CC=200)
    MEDIUM_HIGH = const(2)  # Выше среднего (QMC: 128, MMC: BW=10, RM3100: CC=150)
    BALANCED = const(3)  # Сбалансированный режим (QMC: 128/64, MMC: BW=10, RM3100: CC=100)
    MEDIUM_LOW = const(4)  # Приоритет скорости (QMC: 64, MMC: BW=11, RM3100: CC=75)
    HIGH_SPEED = const(5)  # Макс. скорость опроса, высокий шум (QMC: 64, MMC: BW=11+hpower, RM3100: CC=30-50)


# Именованный кортеж для понятной передачи настроек производительности
PerformanceProfile = namedtuple("PerformanceProfile", "update_rate oversample")

class PerformanceProfiles:
    """Готовые профили производительности (индексы 0-4)."""
    HIGH_ACCURACY = const(0)           # Стационарный компас
    BACKGROUND_MONITORING = const(1)   # Экономия энергии
    DYNAMIC_NAVIGATION = const(2)      # Мобильные роботы, пешая навигация
    TILT_COMPENSATION = const(3)       # Расчет азимута с акселерометром
    FAST_RESPONSE = const(4)           # Простые следящие механизмы


def _axis_name_to_int(axis_name: str) -> int:
    """Преобразует имя оси ('x', 'y', 'z', 'X', 'Y', 'Z') в битовую маску оси: 1(X), 2(Y), 4(Z)"""
    if 1 != len(axis_name):
        raise ValueError(f"len of axis name: {axis_name}")
    an = axis_name.lower()
    if not an[0] in Mag_Axis_Names:
        raise ValueError(f"Invalid axis name: {axis_name}")
    return Mag_Axis_Names.index(an)


def check_axis_index(axis_index: int):
    """Проверяет числовой индекс оси. Он должен быть битовой маской: 1(X), 2(Y) или 4(Z)"""
    if axis_index not in (AXIS_X, AXIS_Y, AXIS_Z):
        raise ValueError(f"Invalid axis index: {axis_index}")


def axis_index_to_name(axis_index: int) -> str:
    """Преобразует битовую маску оси 1(x), 2(y), 4(z) в строку 'x', 'y', 'z'"""
    check_axis_index(axis_index)
    return Mag_Axis_Names[axis_index]


def axis_index_to_reg_addr(axis_index: int, offset: int, multiplier: int) -> int:
    """Преобразует битовую маску оси (1, 2, 4) в адрес регистра.
    Сдвиг >> 1 превращает 1->0, 2->1, 4->2 для корректного расчета адреса.
    """
    check_axis_index(axis_index)
    return offset + multiplier * (axis_index >> 1)


@micropython.native
def _get_min_max(value: float, current_min: float, current_max: float) -> tuple:
    """Возвращает экстремумы value в виде кортежа (current_min, current_max)."""
    if value < current_min:
        current_min = value
    elif value > current_max:
        current_max = value
    return current_min, current_max


@micropython.native
def _arith_mean(value_a: float, value_b: float) -> float:
    """Возвращает среднее арифметическое value_a и value_b."""
    return 0.5 * (value_a + value_b)


class HardIronCalibrator:
    """
    Калибратор магнитометра (компенсация жестких магнитных искажений (Hard Iron)),
    работающий напрямую с объектами MagnetometerData.
    Hard Iron (Жесткое железо) - Это влияние постоянных магнитов или сильно намагниченных ферромагнитных
    деталей рядом с датчиком (например, стальные винты крепления, динамики, моторы).
    Они создают постоянный вектор магнитного поля, который просто сдвигает центр измерений.
    Он не меняется, как бы вы ни вращали датчик.
    """

    def __init__(self):
        # Инициализация бесконечностями для правильного первого сравнения
        self.min_x = float('inf')
        self.max_x = float('-inf')
        self.min_y = float('inf')
        self.max_y = float('-inf')
        self.min_z = float('inf')
        self.max_z = float('-inf')

        self._is_calibrated = False
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        # защита от математической ошибки nan (Not a Number — не число),
        # если пользователь или вызывающий код случайно вызовет метод calculate_offsets()
        self._has_data = False

    def update(self, data: MagnetometerData):
        """
        Обновляет минимальные и максимальные значения на основе объекта MagnetometerData.
        Вызывай этот метод в цикле, пока вращаешь датчик "восьмеркой".
        """
        self._has_data = True
        #
        self.min_x, self.max_x = _get_min_max(data.x, self.min_x, self.max_x)
        self.min_y, self.max_y = _get_min_max(data.y, self.min_y, self.max_y)
        self.min_z, self.max_z = _get_min_max(data.z, self.min_z, self.max_z)

    def calculate_offsets(self) -> tuple:
        """
        Вычисляет вектор смещений (3 float).
        Вызывай этот метод ПОСЛЕ того, как собрал достаточно данных.
        """
        if not self._has_data:
            return 0.0, 0.0, 0.0

        self.offset_x = _arith_mean(self.max_x, self.min_x)
        self.offset_y = _arith_mean(self.max_y, self.min_y)
        self.offset_z = _arith_mean(self.max_z, self.min_z)
        self._is_calibrated = True

        return self.offset_x, self.offset_y, self.offset_z

    def apply(self, data: MagnetometerData) -> MagnetometerData:
        """
        Применяет калибровку к объекту MagnetometerData.
        Возвращает НОВЫЙ объект MagnetometerData с откалиброванными значениями.
        """
        if not self._is_calibrated:
            # Если калибровка не проведена, возвращаем исходный объект без изменений
            return data

        return MagnetometerData(
            x=data.x - self.offset_x,
            y=data.y - self.offset_y,
            z=data.z - self.offset_z,
            is_raw=data.is_raw  # сохраняю флаг формата данных!
        )

    def is_calibrated(self) -> bool:
        return self._is_calibrated


def save_calibration(offsets: tuple, filename: str = "mag_calib.json") -> bool:
    """Сохраняет кортеж смещений (offset_x, offset_y, offset_z) в файл JSON.
    Возвращает True в случае успеха."""
    try:
        with open(filename, "w") as f:
            json.dump(offsets, f)
        return True
    except (OSError, IndexError):
        return False


def load_calibration(filename: str = "mag_calib.json") -> tuple or None:
    """Загружает смещения из JSON файла.
    Возвращает кортеж (offset_x, offset_y, offset_z) или None, если файл поврежден/отсутствует."""
    try:
        with open(filename, "r") as f:
            data = json.load(f)  # Считает список Python

        # проверяю, что массив имеет нужную длину
        if isinstance(data, list) and len(data) == 3:
            return data[0], data[1], data[2]
        return None
    except (OSError, ValueError):
        return None


def tilt_compensate(x: float, y: float, z: float, pitch_rad: float = 0.0, roll_rad: float = 0.0) -> tuple:
    """
    Компенсирует наклон датчика для корректного расчета азимута.

    :param x: Откалиброванное значение магнитного поля по оси X (G)
    :param y: Откалиброванное значение магнитного поля по оси Y (G)
    :param z: Откалиброванное значение магнитного поля по оси Z (G)
    :param pitch_rad: Угол тангажа (наклон вперед/назад) в радианах. По умолчанию 0.0.
    :param roll_rad: Угол крена (наклон влево/вправо) в радианах. По умолчанию 0.0.
    :return: Кортеж (x_comp, y_comp) - компенсированные значения для расчета азимута.
    """
    cos_pitch = math.cos(pitch_rad)
    sin_pitch = math.sin(pitch_rad)
    cos_roll = math.cos(roll_rad)
    sin_roll = math.sin(roll_rad)

    # Матрица поворота для компенсации наклона
    x_comp = x * cos_pitch + z * sin_pitch
    y_comp = x * sin_roll * sin_pitch + y * cos_roll - z * sin_roll * cos_pitch

    return x_comp, y_comp


def _normalize_angle(angle: float) -> float:
    """возвращает нормализованное в диапазон 0 - 360 значение угла."""
    # Нормализация в диапазон 0 - 360
    return angle % 360.0


def get_magnetic_heading(x: float, y: float) -> float:
    """Возвращает магнитный азимут (Magnetic Heading) в градусах (0.0 - 360.0).
    :param x: Компенсированное значение магнитного поля по оси X (G)
    :param y: Компенсированное значение магнитного поля по оси Y (G)
    :return: Азимут в градусах. 0° - Север, 90° - Восток, 180° - Юг, 270° - Запад."""
    # atan2 возвращает угол в радианах от -pi до pi
    heading_rad = math.atan2(y, x)

    # Перевод в градусы
    heading_deg = math.degrees(heading_rad)

    # Нормализация в диапазон 0 - 360
    return _normalize_angle(heading_deg)


def get_true_heading(magnetic_heading: float, declination: float = 0.0) -> float:
    """Возвращает истинный азимут с учетом магнитного склонения.

    :param magnetic_heading: Магнитный азимут (0-360)
    :param declination: Магнитное склонение для вашей местности (в градусах). По умолчанию 0.0.
    :return: Истинный азимут (0-360)"""
    true_heading = magnetic_heading + declination
    # Нормализация в диапазон 0 - 360 и возврат значения
    return _normalize_angle(true_heading)


class IMagnetometer:
    """Интерфейс для магнитометров."""

    def set_magnitude_range_index(self, range_idx: int | None = None) -> int:
        """Устанавливает или возвращает индекс диапазона измерения."""
        raise NotImplementedError()

    def set_update_rate_index(self, index: int | None = None) -> int:
        """Устанавливает или возвращает индекс частоты обновления данных (ODR)."""
        raise NotImplementedError()

    def set_oversample_index(self, index: int | None = None) -> int:
        """Устанавливает или возвращает индекс уровня передискретизации (OSR)."""
        raise NotImplementedError()

    def set_performance_profile(self, profile: int | PerformanceProfile | None = None) -> PerformanceProfile:
        """
        Устанавливает или возвращает профиль производительности (ODR + OSR).
        :param profile: Индекс профиля или именованный кортеж PerformanceProfile.
        :return: Именованный кортеж PerformanceProfile с фактическими значениями.
        """
        raise NotImplementedError()

    def set_continuous_mode(self, value: bool | None = None) -> bool:
        """Устанавливает или возвращает режим непрерывных измерений."""
        raise NotImplementedError()

    def set_raw_mode(self, value: bool | None = None) -> bool:
        """Устанавливает или возвращает режим возврата данных (сырые значения или Гауссы)."""
        raise NotImplementedError()

    def is_data_ready(self) -> bool:
        """Возвращает флаг готовности данных для считывания (data ready). 10.06.2026."""
        raise NotImplementedError()

    def in_standby_mode(self) -> bool:
        """Возвращает True, если датчик находится в режиме низкого энергопотребления (Stand-by/Sleep)."""
        raise NotImplementedError()

    def perform_self_test(self) -> bool | None:
        """Выполняет аппаратное само тестирование. Если оно прошло успешно, возвращает Истина, иначе Ложь.
        Если датчик не поддерживает эту возможность, то возвращает None!

        Встроенный Self Test в дешевых MEMS-магнитометрах (включая HSCDTD008A) – это часто больше маркетинговая функция,
        чем полезный инструмент!"""
        raise NotImplementedError()

    def get_temperature(self) -> int | float | None:
        """Возвращает текущую температуру чипа в градусах Цельсия.

        :return: Температура (float), если датчик имеет встроенный термометр.
                 None, если данная модель датчика физически не имеет
                 встроенного датчика температуры (например, RM3100)."""
        raise NotImplementedError()


class ICommonMagnitometer(IBaseSensorEx, IMagnetometer, Iterator):
    """Общий интерфейс всех (или почти всех) магнитометров."""
    pass