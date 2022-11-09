""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links -- 
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/
"""

import adafruit_sht31d
import board


class TemperatureSensorNotInstantiated(Exception):
    """Raised when the Adafruit SHT3x can not be instantiated."""

    def __init__(self):
        super().__init__("Could not instantiate temperature/humidity sensor.")


class SHT3X:
    """A wrapper around Adafruit's SHT3X temp/humidity sensor driver.

    This class only exists to allow for extensibility if the need arises.
    """

    def __init__(self):
        i2c = board.I2C()
        try:
            self.sensor = adafruit_sht31d.SHT31D(i2c)
            self.sensor.mode = adafruit_sht31d.MODE_SINGLE
        except Exception:
            raise TemperatureSensorNotInstantiated()

    def getRelativeHumidity(self):
        try:
            relative_humidity = self.sensor.relative_humidity
            return relative_humidity
        except Exception as e:
            print(f"Error getting relative humidity: {e}")
            return -1

    def getTemperature(self):
        try:
            temp = self.sensor.temperature
            return temp
        except Exception as e:
            print(f"Error getting temperature: {e}")
            return -1
