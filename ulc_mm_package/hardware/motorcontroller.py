""" DRV8825 - Stepper Motor Controller IC

-- Important Links --
Datasheet:
    https://www.ti.com/lit/ds/symlink/drv8825.pdf
    
*Adapted from Gavin Lyons' RPiMotorLib repository (https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/RpiMotorLib/RpiMotorLib.py)
"""

import enum

from ulc_mm_package.QtGUI.gui_constants import SIMULATION
from ulc_mm_package.hardware.hardware_wrapper import hardware


class Direction(enum.Enum):
    CW = True
    CCW = False
    
class MotorControllerError(Exception):
    """ Base class for catching all motor controller related errors. """

class MotorMoveTimeout(MotorControllerError):
    """ Exception raised when a motor motion takes longer than the allotted time."""

class HomingError(MotorControllerError):
    """ Error raised if an issue occurs during the homing procedure. """

class StopMotorInterrupt(MotorControllerError):
    """ Stop the motor. """

class MotorInMotion(MotorControllerError):
    """ Motor in motion already (i.e in a thread), new motion cannot be started until this one is complete. """

class InvalidMove(MotorControllerError):
    """ Error raised if an invalid move is attempted. """

@hardware
class DRV8825Nema():
    """ Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """
    pass

if __name__ == "__main__":
    print("Instantiating motor...")
    motor = DRV8825Nema(steptype="Full") # Instantiate with all other defaults
    print("Successfully instantiated.")

    print("Beginning homing...")
    motor.homeToLimitSwitches()
    print("Homing complete.")