""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links --
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/


-- References in Code --

[0] https://github.com/adafruit/Adafruit_CircuitPython_SHT31D/blob/84df36e6095ed632b9e1f5206e6149c9c335d365/adafruit_sht31d.py#L237-L240
"""

import time
import board
import threading
import adafruit_sht31d

from typing import Optional, Union, Tuple, List

from ulc_mm_package.hardware.sht31d_temphumiditysensor import (
    TemperatureSensorNotInstantiated,
)


class SHT3X:
    """A wrapper around Adafruit's SHT3X temp/humidity sensor driver.

    This class only exists to allow for extensibility if the need arises.
    """

    def __init__(self, poll_period: float = 1.0):
        """
        `poll_period` is the period of time between pressure sensor polls.
        """
        i2c = board.I2C()
        try:
            self.sensor = adafruit_sht31d.SHT31D(i2c)
            self.sensor.mode = adafruit_sht31d.MODE_SINGLE
        except Exception:
            raise TemperatureSensorNotInstantiated()

        self._halt = threading.Event()
        self._period = poll_period
        self._prev_call = 0.0
        self._th_reading: Optional[Tuple[float, float]] = None

    def start(self):
        self._halt.clear()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def stop(self):
        self._halt.set()
        self._thread.join()

    def _work(self):
        while time.perf_counter() - self._prev_call > self.period:
            if self.halt.is_set():
                return
            self._th_reading = self.sensor._read()

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        if self._th_reading is None:
            if self._halt.is_set():
                raise RuntimeError(
                    "temperature-humidity sensor has been halted - restart or reinstantiate it before polling it"
                )
            else:
                raise RuntimeError("no temperature-humidity value has been retrieved")
        return self._th_reading
