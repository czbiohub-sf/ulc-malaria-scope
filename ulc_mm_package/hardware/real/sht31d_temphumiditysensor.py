""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links --
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/


-- References in Code --

[0] https://github.com/adafruit/Adafruit_CircuitPython_SHT31D/blob/84df36e6095ed632b9e1f5206e6149c9c335d365/adafruit_sht31d.py#L237-L240
"""

import board
import adafruit_sht31d

from typing import Union, Tuple, List

from ulc_mm_package.hardware.sht31d_temphumiditysensor import (
    TemperatureSensorNotInstantiated,
)


class SHT3X:
    """A wrapper around Adafruit's SHT3X temp/humidity sensor driver.

    This class only exists to allow for extensibility if the need arises.
    """

    def __init__(self):
        i2c = board.I2C()
        try:
            self.sensor = adafruit_sht31d.SHT31D(i2c)
            self.sensor.mode = adafruit_sht31d.MODE_SINGLE
            # Don't wait to try to smooth out the signal (w/ repeatability) [0]
            self.sensor.clock_stretching = True
            self.sensor.repeatability = adafruit_sht31d.REP_LOW
        except Exception:
            raise TemperatureSensorNotInstantiated()

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        temperature, humidity = self.sensor._read()
        return temperature, humidity
