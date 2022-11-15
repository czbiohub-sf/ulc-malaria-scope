""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

See RTC under hardware/real/ for more info

"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


@hardware
class RTC_PCF8523:
    """A simplistic (and somewhwat gratuitous) wrapper class for Adafruit's PCF8523 library"""
