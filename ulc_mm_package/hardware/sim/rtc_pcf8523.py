class RTC_PCF8523:
    """A simplistic (and somewhwat gratuitous) wrapper class for Adafruit's PCF8523 library"""

    def __init__(self):
        pass

    def set_time(self, year, month, day, hour, min, sec):
        pass

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
        return "OK"