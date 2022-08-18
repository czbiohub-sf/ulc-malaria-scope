""" PCF8523 - Real-Time Clock (RTC) and Calendar

-- Important Links -- 
Datasheet:
    https://www.nxp.com/docs/en/data-sheet/PCF8523.pdf
Adafruit's PCF8523 Python library:
    https://circuitpython.readthedocs.io/projects/pcf8523/en/latest/ 
"""

import time
import adafruit_pcf8523
import board

from datetime import date

class RTC_PCF8523:
    """A simplistic (and somewhwat gratuitous) wrapper class for Adafruit's PCF8523 library"""

    def __init__(self):
        i2c = board.I2C()
        self.rtc = adafruit_pcf8523.PCF8523(i2c)

    def set_time(self, year, month, day, hour, min, sec):
        date_timetuple = date(year, month, day).timetuple()
        weekday = date_timetuple.tm_wday
        year_day = date_timetuple.tm_yday

        # Set the time using a struct time
        self.rtc.datetime = time.struct_time(
            (year, month, day, hour, min, sec, weekday, year_day, -1)
        )

    def get_time(self):
        """Get the current time from the RTC

        Returns
        -------
        time.struct_time object
            See https://docs.python.org/3/library/time.html#time.struct_time.
            You can access the following attributes from the returned object:
            - tm_year (year)
            - tm_mon (month)
            - tm_mday (day of the month)
            - tm_hour
            - tm_min
            - tm_sec
            - tm_wday (day of the week as a number, ranges from [0-6] with Monday being 0)
            - tm_yday (day of the year, ranges from [1-366])
        """
        return self.rtc.datetime
