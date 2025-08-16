""" DS3231M - Real-Time Clock (RTC) and Calendar

-- Important Links -- 
Datasheet:
    http://datasheets.maximintegrated.com/en/ds/DS3231.pdf
Library from SwitchDoc Labs:
    https://github.com/switchdoclabs/RTC_SDL_DS3231/blob/master/SDL_DS3231.py
"""


import sys
import time
import datetime
import random 
import SDL_DS3231

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT

class RTC_DS3231M:
    """Wrapper class for SwitchDoc Labs RTC library"""

    def __init__(self):
        i2c = board.I2C()
        self.rtc = SDL_DS3231.SDL_DS3231(1, 0x68)

    def sync(self):
        self.rtc.write_now()

    def get_time(self):
        datetime = self.rtc.read_datetime()
        return datetime.strfrtime(DATETIME_FORMAT)
    

if __name__ == "__main__":
    rtc = RTC()
    rtc.sync()

    print("Raspberry Pi=\t" + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("DS3231=\t\t%s" % ds3231.read_datetime())
    print("DS3231 Temp=", ds3231.getTemp())