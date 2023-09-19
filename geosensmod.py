# MicroPython
# mail: goctaprog@gmail.com
# MIT license

from sensor_pack.base_sensor import BaseSensor


class GeoMagneticSensor(BaseSensor):
    """Методы для датчика магнитного поля (Земли в том числе :-) )"""
    def get_axis(self, axis: int) -> [int, tuple]:
        """Возвращает X(axis==0), Y(axis==1) или Z(axis==2) составляющую магнитного поля.
        Returns the X(axis==0), Y(axis==1) or Z(axis==2) component of the magnetic field.
        Если axis = -1, то метод возвращает все составляющие в виде кортежа: X, Y, Z"""
        raise NotImplementedError
