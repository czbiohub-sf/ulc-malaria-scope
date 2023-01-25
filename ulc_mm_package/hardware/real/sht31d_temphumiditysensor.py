""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links --
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/
"""

import board
import adafruit_sht31d

from typing import Tuple, List

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
            self.sensor.mode = adafruit_sht31d.MODE_PERIODIC
            self.sensor.frequency = adafruit_sht31d.FREQUENCY_10
        except Exception:
            raise TemperatureSensorNotInstantiated()

    def _get_most_recent_reading(self, readings: List[float]) -> float:
        """ From the `adafruit_sht31d` package source code:
        'Periodic' mode returns the most recent readings available from the
        sensor's cache in a FILO list of eight floats. This list is backfilled
        with with the sensor's maximum output of 130.0 when the sensor is read
        before the cache is full.
        """

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        temperature, humidity = self.sensor._read()
        return temperature, humidity
