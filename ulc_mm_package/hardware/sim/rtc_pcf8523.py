import time

from datetime import datetime


class RTC_PCF8523:
    """A simplistic (and somewhat gratuitous) wrapper class for Adafruit's PCF8523 library"""

    def __init__(self):
        pass

    def set_time(self, year, month, day, hour, min, sec):
        pass

    def get_time(self):
        datetime_str = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        time_struct = time.strptime(datetime_str, "%Y-%m-%d-%H%M%S")

        return time_struct