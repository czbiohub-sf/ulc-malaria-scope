""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links --
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/
"""


class SHT3X:
    """Simulated temperature/humidity sensor returning dummy values"""

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        temperature, humidity = self.sensor._read()
        return 25.0, 1.0
