""" SHT3x-DIS - Humidity and Temperature Sensor

-- Important Links --
Datasheet:
    https://media.digikey.com/pdf/Data%20Sheets/Sensirion%20PDFs/HT_DS_SHT3x_DIS.pdf
Adafruit's PCF8523 Python library:
    https://docs.circuitpython.org/projects/sht31d/en/latest/
"""

import time
import board
import queue
import threading
import adafruit_sht31d

from typing import Optional, Tuple

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
        self._exception_queue: queue.Queue[Exception] = queue.Queue(maxsize=1)
        self._period = poll_period
        self._prev_call = 0.0
        self._th_reading: Optional[Tuple[float, float]] = None

        self.start()

    def start(self):
        self._halt.clear()
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

        # give a little time to retrieve the first th value
        time.sleep(self._period)

    def stop(self):
        self._halt.set()
        self._thread.join()

    def _work(self):
        while not self._halt.is_set():
            if time.perf_counter() - self._prev_call < self._period:
                time.sleep(self._period / 8)
                continue

            try:
                self._th_reading = self.sensor._read()
            except Exception as e:
                self._halt.set()
                try:
                    self._exception_queue.put_nowait(e)
                except queue.Full:
                    # put the most recent exception in
                    self._exception_queue.get_nowait()
                    self._exception_queue.put_nowait(e)
                    self._exception_queue.task_done()

            self._prev_call = time.perf_counter()

    def get_temp_and_humidity(self) -> Tuple[float, float]:
        try:
            exc = self._exception_queue.get_nowait()
            self._exception_queue.task_done()
            raise exc
        except queue.Empty:
            # if the queue is empty, then there are no exceptions :)
            pass

        if self._th_reading is None:
            if self._halt.is_set():
                raise RuntimeError(
                    "temperature-humidity sensor has been halted - "
                    "restart or reinstantiate it before polling it"
                )
            else:
                raise RuntimeError("no temperature-humidity value has been retrieved")

        return self._th_reading


if __name__ == "__main__":
    th = SHT3X()

    while True:
        print(th.get_temp_and_humidity())
        time.sleep(0.5)
