""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

See pneumatic module under hardware/real/ for more info

"""

import enum

from abc import ABC

from ulc_mm_package.hardware.hardware_wrapper import hardware


class PneumaticModuleError(Exception):
    """Base class for catching all pressure control related errors."""

    pass


class InvalidConfigurationParameters(PneumaticModuleError):
    """Raised if the configuration file has bad parameters for the syringe servo's min/max duty cycle."""


class PressureSensorNotInstantiated(PneumaticModuleError):
    """Raised when the Adafruit MPRLS can not be instantiated."""


class PressureLeak(PneumaticModuleError):
    """Raised when a pressure leak is detected."""


class PressureSensorBusy(PneumaticModuleError):
    """Attempting a read from the mprls sensor but it is still busy."""


class PressureSensorStaleValue(PneumaticModuleError):
    """Raised when the cached value has gone 'stale' (based on a value in hardware_constants.py)"""


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


class PressureSensorRead(enum.Enum):
    """Enum for pressure sensor read status."""

    ALL_GOOD = 0
    SATURATION = 1
    INTEGRITY = 2


class PneumaticModuleBase(ABC):
    def getCurrentDutyCycle(self):
        ...

    def decreaseDutyCycle(self):
        ...

    def increaseDutyCycle(self):
        ...

    def getPressure(self):
        ...
    
    def getAmbientPressure(self):
        ...

    def getMinDutyCycle(self):
        ...

    def getMaxDutyCycle(self):
        ...

    def setDutyCycle(self, duty_cycle: int):
        ...

    def threadedDecreaseDutyCycle(self):
        ...

    def threadedIncreaseDutyCycle(self):
        ...

    def is_locked(self):
        ...


@hardware
class PneumaticModule(PneumaticModuleBase):
    """Class that deals with monitoring and adjusting the pressure.

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """
