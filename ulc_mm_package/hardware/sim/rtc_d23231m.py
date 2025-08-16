from datetime import datetime

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT


class RTC_DS3231M:
    """Wrapper class for SwitchDoc Labs RTC library"""

    def __init__(self):
        pass

    def set_time(self, year, month, day, hour, min, sec):
        pass

    def get_time(self):
        datetime_str = datetime.now().strftime(DATETIME_FORMAT)

        return datetime_str
