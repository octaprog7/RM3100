MicroPython module for control RM3100 Geomagnetic Sensor.

Just connect (VCC, GND, SDA, SCL) from your HSCDTD008A board to Arduino, ESP or any other board with MicroPython firmware.
Attention! In this project, the sensor is connected via the I2C bus. Therefore, it is necessary to connect the A0 and A1 pins of the board to the GND or VCC! Otherwise, EIO exceptions will be thrown!

# Pitch
Before buying a sensor, you need to take care of buying female and male pins with a pitch of 2.0 mm. Additionally, you will have to purchase an adapter board from a pitch of 2.0 to 2.54 mm to connect the sensor to the breadboard!

# Supply
Supply voltage RM3100 3.3 Volts only!

# Upload
Upload micropython firmware to the NANO(ESP, etc) board, and then files: geosensmod.py, main.py, rm3100mod.py and sensor_pack folder. 
Then open main.py in your IDE and run it.

# Pictures
## IDE
![alt text](https://github.com/octaprog7/GeomagneticSensor/blob/master/ide_temp.png)

### Chip temperature sensor
![alt text](https://github.com/octaprog7/GeomagneticSensor/blob/master/ide_temp.png)
### Magnetic field component
![alt text](https://github.com/octaprog7/GeomagneticSensor/blob/master/ide_mag_xyz.png)
## Макетная плата/Bread board
![alt text](https://github.com/octaprog7/GeomagneticSensor/blob/master/board.jpg)
