MicroPython module for control RM3100 Geomagnetic Sensor.

# I2C bus
Just connect (VCC, GND, SDA, SCL) from your HSCDTD008A board to Arduino, ESP or any other board with MicroPython firmware.
Attention! In this project, the sensor is connected via the I2C bus. Therefore, it is necessary to connect the A0(SA0) and A1(SA1) pins of the board to the GND or VCC! Otherwise, EIO exceptions will be thrown!
To enable the I2C bus, you need to connect the first (1) pin of the board, it is etched in the form of a square, to the VCC!

# Pitch
Before buying a sensor, you need to take care of buying female and male pins with a pitch of 2.0 mm. Additionally, you will have to purchase an adapter board from a pitch of 2.0 to 2.54 mm to connect the sensor to the breadboard!
You will have to carefully solder the pins and sockets into the boards.

# Supply
Supply voltage RM3100 3.3 Volts only!

# Upload
Upload micropython firmware to the NANO(ESP, etc) board, and then files: geosensmod.py, main.py, rm3100mod.py and sensor_pack folder. 
Then open main.py in your IDE and run it.

# Pictures
## Default address
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/default_address.png)
## Board view
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/main_view.png)
## PCB Board view
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/master/pcb_view)
## RM3100 on board view
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/rm3100_on_bb.jpg)
## IDE
![alt text](https://github.com/octaprog7/RM3100/blob/master/pic/ide_3100.png)
