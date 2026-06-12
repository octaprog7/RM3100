Модуль MicroPython для управления геомагнитным датчиком RM3100.

# Шина I2C
Просто подключите выводы (VCC, GND, SDA, SCL) от вашей платы RM3100 к Arduino, ESP или любой другой плате с прошивкой MicroPython.
Внимание! В этом проекте датчик подключается по шине I2C. Поэтому необходимо подключить пины платы A0(SA0) и A1(SA1) к GND или VCC! В противном случае будут возникать исключения EIO!
Чтобы включить шину I2C, вам нужно подключить первый (1) пин платы (он вытравлен в виде квадрата) к VCC!

# Шаг разъема
Перед покупкой датчика необходимо позаботиться о приобретении разъемов («мама» и «папа») с шагом 2.0 мм. Кроме того, вам придется приобрести переходную плату с шага 2.0 на 2.54 мм, чтобы подключить датчик к макетной плате!
Вам придется аккуратно припаять пины и гнезда к платам.

# Питание
Напряжение питания RM3100 составляет строго 3.3 Вольта!

# Загрузка
Загрузите прошивку MicroPython на плату NANO (ESP и т. д.), а затем файлы: geosensmod.py, main.py, rm3100mod.py и папку sensor_pack. 
Затем откройте main.py в вашей IDE и запустите его.

# Изображения
## Адрес по умолчанию
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/default_address.png)
## Вид платы
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/main_view.png)
## Вид печатной платы
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/pcb_view.png)
## Переходная плата
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/cross_board_1.jpg)
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/cross_board_2.jpg)
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/cross_board_3.jpg)
## Вид RM3100 на макетной плате
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/rm3100_on_bb.jpg)
## IDE
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/ide_3100.png)
