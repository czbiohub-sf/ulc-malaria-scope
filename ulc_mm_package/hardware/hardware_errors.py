# ==================== Camera errors ===============================
class CameraError(Exception):
    """Base class for catching camera errors."""

    # Note this is temporary until the pyCameras improved exception-handling PR is merged.
    # Once that is merged, we can simply raise the PyCameras error.

# ==================== Motor controller errors ===============================

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