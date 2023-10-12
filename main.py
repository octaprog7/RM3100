# MicroPython
# mail: goctaprog@gmail.com
# MIT license
# import time
# Пожалуйста, прочитайте документацию на RM3100!
# Please read the RM3100 documentation!
from machine import I2C, Pin
import math
import rm3100mod
import time
from sensor_pack.bus_service import I2cAdapter

if __name__ == '__main__':
    # пожалуйста установите выводы scl и sda в конструкторе для вашей платы, иначе ничего не заработает!
    # please set scl and sda pins for your board, otherwise nothing will work!
    # https://docs.micropython.org/en/latest/library/machine.I2C.html#machine-i2c
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) # для примера
    # bus =  I2C(scl=Pin(4), sda=Pin(5), freq=100000)   # на esp8266    !
    # Внимание!!!
    # Замените id=1 на id=0, если пользуетесь первым портом I2C !!!
    # Warning!!!
    # Replace id=1 with id=0 if you are using the first I2C port !!!
    # i2c = I2C(0, scl=Pin(13), sda=Pin(12), freq=400_000) # для примера

    # i2c = I2C(id=1, scl=Pin(27), sda=Pin(26), freq=400_000)  # on Arduino Nano RP2040 Connect and Pico W tested!
    i2c = I2C(id=1, scl=Pin(7), sda=Pin(6), freq=400_000)  # create I2C peripheral at frequency of 400kHz
    adapter = I2cAdapter(i2c)  # адаптер для стандартного доступа к шине
    
    A = "XYZ"
    sensor = rm3100mod.RM3100(adapter)
    print(f"Self Test...")
    st = sensor.perform_self_test()
    b = st[0] and st[1] and st[2]
    print(f"Self Test result: {b}\t{st}")

    print(f"Sensor id: {sensor.get_id()}")
    print(16 * "_")
    for axis in A:
        print(f"{axis} axis cycle count value: {sensor.get_axis_cycle_count(axis)}")

    upd_rate = 6
    sensor.start_measure(axis=A, update_rate=upd_rate, single_mode=True)
    print(f"Is continuous meas mode: {sensor.is_continuous_meas_mode()}")
    print("Single meas mode measurement")
    wt = rm3100mod.get_conversion_cycle_time(upd_rate)
    delay_func = time.sleep_us
    delay_func(wt)
    if sensor.is_data_ready():
        for axis in A:
            print(f"{axis} axis magnetic field value: {sensor.get_meas_result(axis)}")

    print("Continuous meas mode measurement")
    sensor.start_measure(axis=A, update_rate=upd_rate, single_mode=False)
    print(f"Is continuous meas mode: {sensor.is_continuous_meas_mode()}")
    for mag_field_comp in sensor:
        delay_func(wt)
        if mag_field_comp:
            # напряженность магнитного поля в условных ед.
            mfs = math.sqrt(sum(map(lambda val: val ** 2, mag_field_comp)))
            print(f"X: {mag_field_comp[0]}; Y: {mag_field_comp[1]}; Z: {mag_field_comp[2]}; mag field strength: {mfs}")
    # end
    # min_vals = [2**31 for i in range(3)]
    # max_vals = [-2**31 for i in range(3)]
    # while True:
    #    delay_func(wt)
    #    val_0 = sensor.get_meas_result('x')
    #    val_1 = sensor.get_meas_result('y')
    #    val_2 = sensor.get_meas_result('z')
        # min_vals[1] = min(min_vals[1], val)
        # max_vals[1] = max(max_vals[1], val)
        # print(f"y: {val}; min: {min_vals[1]}; max: {max_vals[1]}")
    #    print(val_0, val_1, val_2)
