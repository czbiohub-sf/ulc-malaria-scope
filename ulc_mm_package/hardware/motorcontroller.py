""" DRV8825 - Stepper Motor Controller IC

See motor module under hardware/real/ for more info.

"""

import enum

from ulc_mm_package.hardware.hardware_wrapper import hardware


class Direction(enum.Enum):
    CW = True
    CCW = False


class Steptype(enum.Enum):
    FULL = enum.auto()
    ONE_HALF = enum.auto()  # 1/2
    ONE_QUARTER = enum.auto()  # 1/4
    ONE_EIGHTH = enum.auto()  # 1/8
    ONE_SIXTEENTH = enum.auto()  # 1/16
    ONE_THIRTY_SECOND = enum.auto()  # 1/32
    ONE_SIXTY_FOURTH = enum.auto()  # 1/64
    ONE_ONE_HUNDRED_TWENTY_EIGHTH = enum.auto()  # 1/128


STEP_TYPE_TO_ANGLE = {
    Steptype.FULL: 1.8,
    Steptype.ONE_HALF: 0.9,
    Steptype.ONE_QUARTER: 0.45,
    Steptype.ONE_EIGHTH: 0.225,
    Steptype.ONE_SIXTEENTH: 0.1125,
    Steptype.ONE_THIRTY_SECOND: 0.05625,
    Steptype.ONE_SIXTY_FOURTH: 0.028125,
    Steptype.ONE_ONE_HUNDRED_TWENTY_EIGHTH: 0.0140625,
}

MAX_STEPS_ON_FULL_STEPPING = 450


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


# TODO Convert wrapper hardware classes to ABCs!


@hardware
class DRV8825Nema:
    """Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """

    @property
    def homed(self): ...

    @homed.setter
    def homed(self, v: bool): ...

    @property
    def max_pos(self): ...

    @property
    def pos(self): ...

    def close(self): ...

    def degree_calc(self, steps): ...

    def getCurrentPosition(self): ...

    def getMinimumTravelDistance_um(self): ...

    def isMoveValid(self, dir: Direction, steps: int): ...

    def homeToLimitSwitches(self): ...

    def motor_stop(self, *args): ...

    def _move_rel_steps(self, steps: int, dir=Direction.CCW, stepdelay=0.005): ...

    def move_rel(
        self,
        dir=Direction.CCW,
        steps: int = 200,
        stepdelay=0.005,
        timeout_s: int = int(1e6),
        verbose=False,
        initdelay=0.05,
    ): ...

    def move_abs(
        self, pos: int = 200, stepdelay=0.005, verbose=False, initdelay=0.05
    ): ...

    def threaded_move_rel(self, *args, **kwargs): ...

    def threaded_move_abs(self, *args, **kwargs): ...

    @staticmethod
    def is_locked(): ...
