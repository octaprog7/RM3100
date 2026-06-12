# MicroPython
# mail: goctaprog@gmail.com
# MIT license
# Пожалуйста, прочитайте документацию на RM3100!
# Please read the RM3100 documentation!
import math
import time
from machine import I2C, Pin
from micropython import const

from rm3100mod import RM3100
from sensor_pack_2.geosensmod import (HardIronCalibrator, MagRange, ICommonMagnitometer,
                                      UpdateRates, OversampleLevels, PerformanceProfiles, AXIS_ALL)
from sensor_pack_2.bus_service import I2cAdapter

I2C_ID = const(1)
SCL_PIN = const(7)
SDA_PIN = const(6)
I2C_FREQ = const(100_000)  # 100 кГц для стабильной работы с BMP390 на одной шине
SENSOR_ADDR = const(0x20)
ITERATIONS = const(15)

calibration_on: bool = True


def run_calibration(sens: ICommonMagnitometer, duration_ms=15_000) -> HardIronCalibrator:
    """Проводит процедуру калибровки."""
    width = 60
    print("\n" + "=" * width)
    print(" КАЛИБРОВКА ДАТЧИКА (Hard Iron Compensation)")
    print("=" * width)
    print("ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ:")
    print("Убедитесь, что рядом нет посторонних магнитов или металла.")
    print("Медленно вращайте датчик во всех направлениях (восьмерка/сфера).")
    print(f"Продолжайте вращение в течение {0.001 * duration_ms} секунд.")
    print("=" * width)

    # ВРЕМЯ ПОДГОТОВИТЬСЯ И ВЗЯТЬ ПЛАТУ С ДАТЧИКОМ В РУКИ!
    print("\nПодготовьтесь... Начало сбора данных через 3 секунды.")
    time.sleep(3)

    # Получаем реальный период опроса из настроек датчика
    poll_delay = sens.get_conversion_cycle_time()
    print(f"Период опроса: {poll_delay} мс")

    # Проверка: убедимся, что датчик в непрерывном режиме
    if not sens.is_continuously_mode():
        print("ВНИМАНИЕ: Датчик НЕ в непрерывном режиме! Перезапускаю...")
        sens.set_continuous_mode(True)
        sens.start_measurement()
        time.sleep_ms(100)

    print("Сбор данных запущен! Начинайте вращать датчик...")

    cal = HardIronCalibrator()
    start_time = time.ticks_ms()
    samples = 0
    drdy_checks = 0

    while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
        if sens.is_data_ready():
            # Прямой вызов вместо next(sens) — без двойной проверки
            data = sens.get_measurement_value(AXIS_ALL)
            if data is not None:
                cal.update(data)
                samples += 1
                if samples % 50 == 0:
                    print(".", end="")
        else:
            drdy_checks += 1
        time.sleep_ms(poll_delay)

    print(f"\nСбор данных завершен. Собрано образцов: {samples}")
    print(f"Проверок DRDY без данных: {drdy_checks}")

    if samples < 1000:
        print("ВНИМАНИЕ: Собрано слишком мало данных. Калибровка может быть неточной.")

    cal.calculate_offsets()
    return cal


def show_calibration_offsets(cal: HardIronCalibrator):
    """Выводит вычисленные смещения (offsets) калибратора в консоль."""
    width = 45
    print("\n" + "=" * width)
    print(" РЕЗУЛЬТАТЫ КАЛИБРОВКИ (Смещения)")
    print("=" * width)
    if cal.is_calibrated():
        print(f" Смещение по оси X (Offset X): {cal.offset_x:>8.4f} G")
        print(f" Смещение по оси Y (Offset Y): {cal.offset_y:>8.4f} G")
        print(f" Смещение по оси Z (Offset Z): {cal.offset_z:>8.4f} G")
    else:
        print(" Калибровка не выполнена. Смещения равны 0.0000 G")
    print("=" * width + "\n")


def show_mode(sen: ICommonMagnitometer):
    """
    Выводит текущие настройки и статус датчика RM3100 в консоль.
    Идеально подходит для отладки и проверки состояния оборудования.

    :param sen: Экземпляр класса RM3100
    """
    width = 40
    print("=" * width)
    print("       Состояние датчика RM3100       ")
    print("=" * width)

    # Режим измерений
    mode_str = "Непрерывный" if sen.is_continuously_mode() else "Ожидание"
    print(f"Режим измерений: {mode_str}")

    # Формат возвращаемых данных
    format_str = "Raw (LSB)" if True == sen.set_raw_mode() else "Гауссы"
    print(f"Формат возвращаемых данных: {format_str}")

    # Частота обновления (ODR)
    odr_idx = sen.set_update_rate_index()
    print(f"Частота обновления: Index {odr_idx}")

    # Диапазон измерений (Full Scale)
    fs_str = "8 Gauss" if MagRange.G8 == sen.set_magnitude_range_index() else "2 Gauss"
    print(f"Диапазон измерений: {fs_str}")

    # Cycle Count (аналог Oversample Ratio)
    cc_idx = sen.set_oversample_index()
    print(f"аналог Oversample Ratio: Index {cc_idx}")

    print("-" * width)

    # Текущие флаги статуса (у RM3100 только DRDY)
    try:
        status = sen.get_data_status(raw=False)
        drdy_str = "Данные готовы" if status.DataReady else "Данные не готовы"
        print(f"Флаг: DRDY: {drdy_str}")
    except Exception as e:
        print(f"Status Flag     : Error reading status ({e})")

    print("=" * width)


if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    i2c = I2C(id=I2C_ID, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
    adapter = I2cAdapter(i2c)  # адаптер для стандартного доступа к шине
    delay_func = time.sleep_ms

    sensor = RM3100(adapter, address=SENSOR_ADDR)
    print(f"id датчика: {sensor.get_id()}")
    print(16 * "_")

    # =====================================================================
    # ИНТЕРАКТИВНЫЙ ЗАПРОС НА КАЛИБРОВКУ.
    # Настраиваю датчик в стабильный режим для сбора данных калибровки.
    # =====================================================================

    # СБРОС датчика к заводским настройкам (убирает "зависания")
    print("\nВыполняю soft_reset()...")
    sensor.soft_reset()
    delay_func(100)  # Даем время на стабилизацию

    # RM3100 всегда 8 Gauss (однодиапазонный датчик)
    sensor.set_magnitude_range_index(MagRange.G8)

    # ЯВНО устанавливаем параметры для калибровки (150 Hz)
    sensor.set_update_rate_index(UpdateRates.HZ_100)  # Index 2 = ~150 Hz
    sensor.set_oversample_index(OversampleLevels.BALANCED)  # CC=100

    sensor.set_continuous_mode(True)
    sensor.set_raw_mode(False)    # данные сразу в Гауссах

    sensor.start_measurement()

    # ВАЖНО: Задержка после запуска измерений!
    print("Жду 100 мс для стабилизации...")
    delay_func(100)

    # ПРОВЕРКА: Жду готовности данных
    print("Ожидание DRDY...")
    for i in range(10):
        if sensor.is_data_ready():
            print(f"DRDY готов после {i*10} мс")
            break
        delay_func(10)
    else:
        print("DRDY не(!) готов после 100 мс!")

    # отображение текущего режима датчика
    show_mode(sensor)

    if not calibration_on:
        print("Калибровка пропущена. Используются нулевые смещения.")
        clbr = HardIronCalibrator()
    else:
        clbr = run_calibration(sensor)
        show_calibration_offsets(clbr)

    # =====================================================================
    # БЛОК ИЗМЕРЕНИЙ: RM3100 всегда работает в диапазоне ±8 Gauss
    # =====================================================================
    sensor.set_magnitude_range_index(MagRange.G8)  # RM3100 всегда 8 Gauss
    sensor.set_performance_profile(PerformanceProfiles.DYNAMIC_NAVIGATION)  # 37 Hz, CC=100
    sensor.set_continuous_mode(True)
    sensor.start_measurement()

    # отображение текущего режима датчика
    show_mode(sensor)
    wt = sensor.get_conversion_cycle_time()
    delay_func(wt // 2)

    print("\n--- Измерения: 8 Gauss Range (DYNAMIC_NAVIGATION) ---")
    delay_func(wt * 3)  # жду 3 цикла для стабилизации внутренних цепей после смены режима!

    index = 0
    for mf_comp in sensor:
        delay_func(wt)
        if mf_comp:
            cal_data = clbr.apply(mf_comp)
            magnitude = math.sqrt(cal_data.x * cal_data.x + cal_data.y * cal_data.y + cal_data.z * cal_data.z)
            print(
                f"X: {cal_data.x:.4f}; Y: {cal_data.y:.4f}; Z: {cal_data.z:.4f}; {magnitude:.4f} [G]")
        index += 1
        if index > ITERATIONS:
            break

    print("\nГотово!")