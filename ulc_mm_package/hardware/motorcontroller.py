""" DRV8825 - Stepper Motor Controller IC

See motor module under hardware/real/ for more info.

"""

import enum

from ulc_mm_package.hardware.hardware_wrapper import hardware


class Direction(enum.Enum):
    CW = True
    CCW = False


class MotorControllerError(Exception):
    """Base class for catching all motor controller related errors."""


class MotorMoveTimeout(MotorControllerError):
    """Exception raised when a motor motion takes longer than the allotted time."""


class HomingError(MotorControllerError):
    """Error raised if an issue occurs during the homing procedure."""


class StopMotorInterrupt(MotorControllerError):
    """Stop the motor."""


class MotorInMotion(MotorControllerError):
    """Motor in motion already (i.e in a thread), new motion cannot be started until this one is complete."""


class InvalidMove(MotorControllerError):
    """Error raised if an invalid move is attempted."""


# TODO I am not sure the "correct" way to type these wrapped classes?


@hardware
class DRV8825Nema:
    """Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """

    @property
    def homed(self):
        ...

    @homed.setter
    def homed(self, v: bool):
        ...

    @property
    def max_pos(self):
        ...

    @property
    def pos(self):
        ...

    def close(self):
        ...

    def degree_calc(self, steps):
        ...

    def getCurrentPosition(self):
        ...

    def getMinimumTravelDistance_um(self):
        ...

    def isMoveValid(self, dir: Direction, steps: int):
        ...

    def homeToLimitSwitches(self):
        ...

    def motor_stop(self, *args):
        ...

    def _move_rel_steps(self, steps: int, dir=Direction.CCW, stepdelay=0.005):
        ...

    def move_rel(
        self,
        dir=Direction.CCW,
        steps: int = 200,
        stepdelay=0.005,
        timeout_s: int = int(1e6),
        verbose=False,
        initdelay=0.05,
    ):
        ...

    def move_abs(self, pos: int = 200, stepdelay=0.005, verbose=False, initdelay=0.05):
        ...

    def threaded_move_rel(self, *args, **kwargs):
        ...

    def threaded_move_abs(self, *args, **kwargs):
        ...


# TODO Move this and other hardware testing code into a single unified script/folder
if __name__ == "__main__":
    print("Instantiating motor...")
    motor = DRV8825Nema(steptype="Full")  # Instantiate with all other defaults
    print("Successfully instantiated.")

    print("Beginning homing...")
    motor.homeToLimitSwitches()
    print("Homing complete.")
