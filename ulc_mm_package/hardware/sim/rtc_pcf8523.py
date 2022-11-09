from datetime import datetime

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT

class RTC_PCF8523:
    """A simplistic (and somewhat gratuitous) wrapper class for Adafruit's PCF8523 library"""

    def __init__(self):
        pass

    def set_time(self, year, month, day, hour, min, sec):
        pass

    def get_time(self):
        datetime_str = datetime.now().strftime(DATETIME_FORMAT)

        return datetime_str