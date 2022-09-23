""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

See pneumatic module under hardware/real/ for more info

"""

import enum
import functools
import threading
import pigpio
import board
import adafruit_mprls

from time import sleep, perf_counter

from ulc_mm_package.hardware.hardware_wrapper import hardware
from ulc_mm_package.hardware.hardware_constants import *
from ulc_mm_package.hardware.dtoverlay_pwm import (
    dtoverlay_PWM,
    PWM_CHANNEL,
)


class PneumaticModuleError(Exception):
    """Base class for catching all pressure control related errors."""
    pass

class PressureSensorNotInstantiated(PneumaticModuleError):
    """Raised when the Adafruit MPRLS can not be instantiated."""

class PressureLeak(PneumaticModuleError):
    """Raised when a pressure leak is detected."""

class SyringeInMotion(PneumaticModuleError):
    pass

class SyringeEndOfTravel(PneumaticModuleError):
    """
    Raised when the syringe is at its end-of-travel in a direction
    and but another move in that direction is requested
    """
    pass

class SyringeDirection(enum.Enum):
    """Enum for the direction of the syringe."""
    UP = 1
    DOWN = -1

@hardware
class PneumaticModule():
    """Class that deals with monitoring and adjusting the pressure.

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """
