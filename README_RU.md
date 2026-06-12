# MicroPython драйвер геомагнитного датчика RM3100

Библиотека на языке MicroPython для работы с высокоточным геомагнитным датчиком (магнитометром) **RM3100** по интерфейсу I2C. Драйвер спроектирован с учетом оптимизации скорости считывания данных и поддерживает как сырые отсчеты АЦП, так и автоматическую конвертацию физических величин в Гауссы (G).

---

## Особенности модуля
* **Высокая скорость**: чтение всех трех осей (X, Y, Z) выполняется за одну транзакцию по шине I2C.
* **Гибкие режимы работы**: поддержка однократных замеров (Single/POLL) и режима непрерывного сканирования (Continuous Measurement Mode / CMM).
* **Профили производительности**: предустановленные готовые пресеты (`HIGH_ACCURACY`, `BACKGROUND_MONITORING`, `DYNAMIC_NAVIGATION`, `TILT_COMPENSATION`, `FAST_RESPONSE`).
* **Контроль передискретизации**: тонкая настройка счетчика циклов (Cycle Count) от 30 до 400 для регулирования уровня шума и разрешения.
* **Инструменты диагностики**: встроенная функция аппаратной самопроверки датчика (BIST).
* **Программный сброс**: метод `soft_reset()` для безопасной инициализации и очистки зависших состояний чипа.

---

## Схема подключения (I2C)
Датчик RM3100 поддерживает аппаратные адреса в диапазоне `0x20`–`0x23`.

| RM3100 Pin | ESP32 / STM32 / RP2040 Pin | Описание           |
|:-----------|:---------------------------|:-------------------|
| **VCC**    | 3.3V                       | Питание датчика    |
| **GND**    | GND                        | Земля              |
| **SCL**    | I2C SCL (например, GPIO 7) | Тактовая линия I2C |
| **SDA**    | I2C SDA (например, GPIO 6) | Линия данных I2C   |

**ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ:** 
* Линии аппаратного выбора адреса **SA0** и **SA1** на плате датчика необходимо **обязательно** жестко подтянуть к **VCC** или **GND** для задания конкретного адреса! 
Если оставить эти пины в «плавающем» состоянии (никуда не подключенными), адрес устройства будет хаотично меняться, а обмен данными с датчиком будет постоянно сбоить!!!
* Для обмена по I2C, подключите вывод платы датчика I2C/SPI к VCC (+3.3 В)!

![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/pcb_view.png)
---

## Быстрый старт

### 1. Базовое чтение данных (в Гауссах)
По умолчанию драйвер инициализирует датчик в режиме `TILT_COMPENSATION` (~150 Гц) и автоматически переводит сырые значения в Гауссы.

```python
from machine import I2C, Pin
from sensor_pack_2.bus_service import I2cAdapter
from rm3100 import RM3100
import time

# Инициализация I2C шины MicroPython
i2c = I2C(0, scl=Pin(7), sda=Pin(6), freq=100000)
adapter = I2cAdapter(i2c)

# Создание экземпляра класса датчика (адрес по умолчанию 0x20)
sensor = RM3100(adapter=adapter, address=0x20)

# Запуск однократного измерения по всем осям
sensor.start_measurement()

# Ожидание готовности данных
while not sensor.is_data_ready():
    time.sleep_ms(5)

# Получение результата в Гауссах (G)
data = sensor.get_measurement_value()
print(f"X: {data.x:.4f} G, Y: {data.y:.4f} G, Z: {data.z:.4f} G")
```

### 2. Чтение в режиме непрерывных измерений (CMM)
В данном примере используется потоковый опрос датчика с помощью встроенного итератора `__next__`.

```python
# Настройка непрерывного режима работы
sensor.set_continuous_mode(True)
sensor.start_measurement()

print("Сбор данных в непрерывном режиме...")
try:
    while True:
        # Извлечение данных, если они обновились в регистре датчика
        data = next(sensor)
        if data is not None:
            print(f"Магнитное поле [G] -> X: {data.x:.3f} | Y: {data.y:.3f} | Z: {data.z:.3f}")
        
        # Задержка на период обновления данных датчика
        time.sleep_ms(sensor.get_conversion_cycle_time())
except KeyboardInterrupt:
    # Остановка непрерывного режима при прерывании
    sensor.set_continuous_mode(False)
    sensor.start_measurement()
```

### 3. Получение сырых данных (ADC counts)
Если вам требуются безразмерные сырые значения напрямую из АЦП магнитометра, переключите режим методом `set_raw_mode`:

```python
sensor.set_raw_mode(True)
sensor.start_measurement()

while not sensor.is_data_ready():
    pass

raw_data = sensor.get_measurement_value()
print(f"Сырые отсчеты АЦП -> X: {raw_data.x} | Y: {raw_data.y} | Z: {raw_data.z}")
```

---

## Калибровка датчика и компенсация помех (Hard Iron)

Для получения точных данных (например, при расчете курса или создании цифрового компаса) датчик необходимо откалибровать, чтобы исключить влияние постоянных магнитных полей от компонентов платы, батарей или элементов корпуса. 

Скрипт `main.py` реализует интерактивную процедуру: переводит датчик в быстрый режим (~150 Гц), собирает калибровочные точки в течение 15 секунд во время вращения платы пользователем, вычисляет смещения осей и выводит компенсированные значения вместе с результирующим вектором магнитного поля.

```python
import math
import time
from machine import I2C, Pin
from micropython import const
from rm3100mod import RM3100
from sensor_pack_2.geosensmod import (HardIronCalibrator, MagRange, 
                                      UpdateRates, OversampleLevels, 
                                      PerformanceProfiles, AXIS_ALL)
from sensor_pack_2.bus_service import I2cAdapter

# Настройки периферии
I2C_ID = const(1)
SCL_PIN = const(7)
SDA_PIN = const(6)
I2C_FREQ = const(100_000)
SENSOR_ADDR = const(0x20)
ITERATIONS = const(15)

def run_calibration(sens, duration_ms=15_000) -> HardIronCalibrator:
    """Процедура сбора данных для калибровки Hard Iron."""
    print("\n" + "=" * 60)
    print(" КАЛИБРОВКА ДАТЧИКА (Hard Iron Compensation)")
    print("=" * 60)
    print("ИНСТРУКЦИЯ: Убедитесь, что рядом нет магнитов или металла.")
    print("Медленно вращайте датчик во всех направлениях (по сфере/восьмеркой).")
    print(f"Продолжайте вращение в течение {0.001 * duration_ms} секунд.")
    print("=" * 60)
    
    print("\nПодготовьтесь... Начало сбора данных через 3 секунды.")
    time.sleep(3)
    
    poll_delay = sens.get_conversion_cycle_time()
    
    if not sens.is_continuously_mode():
        sens.set_continuous_mode(True)
        sens.start_measurement()
        time.sleep_ms(100)
        
    print("Сбор запущен! Начинайте вращать датчик...")
    cal = HardIronCalibrator()
    start_time = time.ticks_ms()
    samples = 0
    
    while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
        if sens.is_data_ready():
            data = sens.get_measurement_value(AXIS_ALL)
            if data is not None:
                cal.update(data)
                samples += 1
                if samples % 50 == 0:
                    print(".", end="")
        time.sleep_ms(poll_delay)
        
    print(f"\nСбор данных завершен. Собрано образцов: {samples}")
    cal.calculate_offsets()
    return cal

# Инициализация аппаратной части
i2c = I2C(id=I2C_ID, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
adapter = I2cAdapter(i2c)
sensor = RM3100(adapter, address=SENSOR_ADDR)

print(f"ID ревизии чипа датчика: {sensor.get_id()}")

# Программный сброс датчика перед стартом для предотвращения зависаний
print("\nВыполняю soft_reset()...")
sensor.soft_reset()
time.sleep_ms(100)

# Явно устанавливаем быстрые параметры для калибровки (150 Hz)
sensor.set_magnitude_range_index(MagRange.G8)
sensor.set_update_rate_index(UpdateRates.HZ_100) # ~150 Hz
sensor.set_oversample_index(OversampleLevels.BALANCED) # CC=100
sensor.set_continuous_mode(True)
sensor.set_raw_mode(False) # Данные в Гауссах
sensor.start_measurement()
time.sleep_ms(100)

# Запуск интерактивной калибровки
clbr = run_calibration(sensor)

print(f"Смещение X: {clbr.offset_x:.4f} G | Y: {clbr.offset_y:.4f} G | Z: {clbr.offset_z:.4f} G")

# Перевод датчика в рабочий режим (динамическая навигация, ~37 Гц, CC=100)
sensor.set_performance_profile(PerformanceProfiles.DYNAMIC_NAVIGATION)
sensor.set_continuous_mode(True)
sensor.start_measurement()

wt = sensor.get_conversion_cycle_time()
time.sleep_ms(wt * 3) # Стабилизация внутренних цепей после смены режима

print("\n--- Измерения: 8 Gauss Range (DYNAMIC_NAVIGATION) ---")
count = 0
for mf_comp in sensor:
    time.sleep_ms(wt)
    if mf_comp:
        # Применение вычисленных калибровочных смещений
        cal_data = clbr.apply(mf_comp)
        # Расчет полной напряженности (модуля магнитной индукции)
        magnitude = math.sqrt(cal_data.x**2 + cal_data.y**2 + cal_data.z**2)
        
        print(f"X: {cal_data.x:.4f}; Y: {cal_data.y:.4f}; Z: {cal_data.z:.4f} | Итого: {magnitude:.4f} [G]")
        
        count += 1
        if count > ITERATIONS:
            break
print("\nГотово!")
```

## Основные методы API

* **`setup()`**
  Базовая первоначальная конфигурация устройства и установка дефолтного профиля.
* **`start_measurement()`**
  Отправляет команду на триггер измерения в зависимости от текущего режима (`_single_mode` или `continuous`).
* **`is_data_ready() -> bool`**
  Возвращает `True`, если датчик завершил преобразование и данные готовы к чтению.
* **`get_measurement_value(axis=AXIS_ALL) -> MagnetometerData`**
  Считывает результаты. Возвращает именованный кортеж с полями `x`, `y`, `z` и флагом `is_raw`.
* **`set_performance_profile(profile)`**
  Установка профиля работы (от `0` до `4`): `HIGH_ACCURACY`, `BACKGROUND_MONITORING`, `DYNAMIC_NAVIGATION`, `TILT_COMPENSATION`, `FAST_RESPONSE`.
* **`set_axis_cycle_count(axis, value)`** 
  Ручная установка количества циклов передискретизации для конкретной оси (допустимо от 30 до 400).
* **`get_conversion_cycle_time() -> int`** 
  Возвращает период обновления данных (1/ODR) в миллисекундах для текущих настроек датчика.
* **`get_adc_conversion_time() -> int`** 
  Возвращает чистое время работы АЦП в микросекундах (мкс) по формуле из даташита.
* **`perform_self_test() -> bool`** 
  Запускает встроенное аппаратное тестирование осей (BIST). Возвращает `True`, если устройство исправно.
* **`soft_reset()`** 
  Сброс настроек чипа к заводским параметрам по умолчанию (~37 Гц, Cycle Count = 200) и синхронизация внутреннего состояния драйвера (1.pdf pp. 5-6).



## Лицензия
Данный программный код распространяется под лицензией **MIT**
