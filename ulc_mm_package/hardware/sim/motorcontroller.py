import time
import logging
import threading

import pigpio

from typing import Optional

from ulc_mm_package.utilities.lock_utils import lock_no_block
from ulc_mm_package.hardware.hardware_constants import (
    FULL_STEP_TO_TRAVEL_DIST_UM,
    DEFAULT_FULL_STEP_HOMING_TIMEOUT,
    MOTOR_ENABLE,
    MOTOR_SLEEP,
    MOTOR_RESET,
    MOTOR_STEP_PIN,
    MOTOR_DIR_PIN,
    MOTOR_FAULT_PIN,
    MOTOR_LIMIT_SWITCH1,
    ZERO_OFFSET_STEPS,
)
from ulc_mm_package.hardware.motorcontroller import (
    Direction,
    MotorControllerError,
    MotorMoveTimeout,
    StopMotorInterrupt,
    MotorInMotion,
    InvalidMove,
    Steptype,
    STEP_TYPE_TO_ANGLE,
    MAX_STEPS_ON_FULL_STEPPING,
)
from ulc_mm_package.hardware.real.motorcontroller import DRV8825Nema as RealDRV8825Nema


MOTOR_LOCK = threading.Lock()


class DRV8825Nema(RealDRV8825Nema):
    """Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """

    def __init__(
        self,
        direction_pin=MOTOR_DIR_PIN,
        step_pin=MOTOR_STEP_PIN,
        enable_pin=MOTOR_ENABLE,
        sleep_pin=MOTOR_SLEEP,
        reset_pin=MOTOR_RESET,
        fault_pin=MOTOR_FAULT_PIN,
        motor_type="DRV8825",
        steptype=Steptype.ONE_HALF,
        lim1=MOTOR_LIMIT_SWITCH1,
        lim2: Optional[int] = None,
        max_pos: Optional[int] = None,
        pi: "pigpio.pi" = None,
    ):
        """
        Parameters
        ----------
        direction : int
            GPIO pin connected to DIR pin of IC
        step_pin : int
            GPIO pin connected to STEP of IC
        motor_type : string
            Type of motor two options: A4988 or DRV8825
        steptype : string
            Type of drive to step motor, options:
            (Full, Half, 1/4, 1/8, 1/16, 1/32) for DRV8825 only
        lim1 : int
            Limit switch 1 GPIO pin
        lim2 : int
            Limit switch 2 GPIO pin (defaults to None, i.e no secondary limit switch)
        pi : pigpio.pi()
            Optional parameter to pass an existing pigpio.pi() object. This would be passed in for cases where you may want two or more hardware objects to
            both use the same callback thread
        """
        self.logger = logging.getLogger(__name__)

        self.motor_type = motor_type
        self.direction_pin = direction_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.sleep_pin = sleep_pin
        self.reset_pin = reset_pin
        self.fault_pin = fault_pin
        self.lim1 = lim1
        self.lim2 = lim2
        self.steptype = steptype
        self.pos = int(1e6)
        self._homed = False
        self.stop_motor = False

        # Get step degree based on steptype
        self.step_degree = STEP_TYPE_TO_ANGLE[steptype]
        self.microstepping = (
            STEP_TYPE_TO_ANGLE[Steptype.FULL] / self.step_degree
        )  # 1, 2, 4, 8, 16, 32
        self.dist_per_step_um = (
            self.step_degree
            / STEP_TYPE_TO_ANGLE[Steptype.FULL]
            * FULL_STEP_TO_TRAVEL_DIST_UM
        )

        # TODO Calculate the max position allowable based on stepping mode and actual travel distance on the scope
        self.max_pos = (
            int(max_pos)
            if isinstance(max_pos, int)
            else int(MAX_STEPS_ON_FULL_STEPPING * self.microstepping)
        )

        # Set up GPIO
        # Move motor up to ensure it isn't hitting the limit switch
        self._move_rel_steps(
            steps=int(ZERO_OFFSET_STEPS * self.microstepping), dir=Direction.CW
        )

    @property
    def homed(self):
        return self._homed

    @homed.setter
    def homed(self, v: bool):
        self._homed = bool(v)

    def close(self):
        pass

    def getCurrentPosition(self):
        return self.pos

    def homeToLimitSwitches(self):
        """Move to the limit switch and the set the zero position (with an offset).

        If a second limit switch is present, move to that one and set the max position.
        """

        # Adjust the timeout based on the microstepping mode
        homing_timeout = DEFAULT_FULL_STEP_HOMING_TIMEOUT * self.microstepping

        self.logger.info("Waiting for motor to finish homing.")

        # Move the motor until it hits the CCW limit switch
        try:
            # override homing_timeout so we dont wait forever
            homing_timeout = 5
            self.move_rel(dir=Direction.CCW, steps=1e6, timeout_s=homing_timeout)
        except MotorMoveTimeout:
            # normally we would throw this error, but we do not hit limit switches
            # so this will suffice
            self.pos = 0
            """
            raise HomingError(
                f"Motor failed to home in the allotted time ({homing_timeout} seconds)."
            )
            """
        except StopMotorInterrupt:
            # Move slightly until the limit switch is no longer active
            self.pos = 0

        if self.lim2 is not None:
            # Move to the CW limit switch
            try:
                self.move_rel(dir=Direction.CW, steps=1e6, timeout_s=homing_timeout)
            except MotorMoveTimeout:
                # normally we would throw this error, but we do not hit limit switches
                # so this will suffice
                self.max_pos = int(450 * self.microstepping)
                """
                raise HomingError(
                    f"Motor failed to home in the allotted time ({homing_timeout} seconds)."
                )
                """
            except StopMotorInterrupt:
                self.max_pos = self.pos

        self.logger.info("Done homing motor.")
        self.homed = True

    def _move_rel_steps(self, steps: int, dir=Direction.CCW, stepdelay=0.005):
        step_increment = 1 if dir else -1
        for i in range(steps):
            # our app is heavily dependent on timing, lets keep the `sleep`s in
            time.sleep(stepdelay)
            time.sleep(stepdelay)
            self.pos += step_increment

    @lock_no_block(MOTOR_LOCK, MotorInMotion)
    def move_rel(
        self,
        dir=Direction.CCW,
        steps: int = 200,
        stepdelay=0.005,
        timeout_s: int = int(1e6),
        verbose=False,
        initdelay=0.05,
    ):
        """Move the motor a relative number of steps (if the move is valid).

        Parameters
        ----------
        dir : Direction enum
        steps : int
            Number of steps Default is 200 (one revolution in Full mode)
        stepdelay : float
            Time to wait (in seconds) between steps
        verbose : bool
        initdelay : float
            Intial delay after GPIO pins initialized but before motor is moved
        """

        self.stop_motor = False
        steps = int(steps)
        step_increment = 1 if dir.value else -1

        if self.homed:
            if not self.isMoveValid(dir, steps):
                direction = "CW (+)" if dir.value else "CCW (-)"
                raise InvalidMove(
                    f"""
                =======INVALID MOVE, OUT OF RANGE=======
                Current position: {self.pos}\n
                Attempted direction: {direction}\n
                Attempted steps: {steps}\n
                Allowable range: 0 <= steps <= {self.max_pos}\n
                Attempted move would result in: {self.pos + step_increment*steps}
                """
                )
        try:
            time.sleep(initdelay)
            start_pos = self.pos
            start_time = time.perf_counter()

            for i in range(steps):
                if self.stop_motor:
                    raise StopMotorInterrupt()
                else:
                    time.sleep(stepdelay)
                    time.sleep(stepdelay)
                    self.pos += step_increment

                    if time.perf_counter() - start_time >= timeout_s:
                        raise MotorMoveTimeout()
                    if verbose:
                        self.logger.debug(f"Steps {i} \ Position: {self.pos}")

        except KeyboardInterrupt:
            raise MotorControllerError("User keyboard interrupt")
        except StopMotorInterrupt:
            raise
        except MotorMoveTimeout:
            raise
        except Exception:
            raise MotorControllerError("Unexpected error in move_rel")

        finally:
            # Print report status
            if verbose:
                self.logger.debug("\nRpiMotorLib, Motor Run finished, Details:.\n")
                self.logger.debug("Motor type = {}".format(self.motor_type))
                self.logger.debug("Direction = {}".format(dir))
                self.logger.debug("Step Type = {}".format(self.steptype))
                self.logger.debug("Number of steps = {}".format(self.pos - start_pos))
                self.logger.debug("Step Delay = {}".format(stepdelay))
                self.logger.debug("Intial delay = {}".format(initdelay))
                self.logger.debug(
                    "Size of turn in degrees = {}".format(self.degree_calc(steps))
                )

    @lock_no_block(MOTOR_LOCK, MotorInMotion)
    def move_abs(self, pos: int = 200, stepdelay=0.005, verbose=False, initdelay=0.05):
        """Move the motor to the given position (if valid).

        Parameters
        ----------
        pos : int
            Number of steps Default is 200 (one revolution in Full mode)
        stepdelay : float
            Time to wait (in seconds) between steps
        verbose : bool
        initdelay : float
            Intial delay after GPIO pins initialized but before motor is moved
        """

        self.stop_motor = False
        step_increment = 1 if self.pos < pos else -1

        # Set direction
        dir = Direction.CW if step_increment == 1 else Direction.CCW

        # Calculate steps to take and check if valid
        steps = (pos - self.pos) * step_increment
        if self.homed:
            if not self.isMoveValid(dir, steps):
                direction = "CW (+)" if step_increment == 1 else "CCW (-)"
                raise InvalidMove(
                    f"""
                =======INVALID MOVE, OUT OF RANGE=======
                Current position: {self.pos}\n
                Attempted direction: {direction}\n
                Attempted steps: {steps}\n
                Allowable range: 0 <= steps <= {self.max_pos}\n
                Attempted move would result in: {self.pos + step_increment*steps}
                """
                )

        try:
            time.sleep(initdelay)
            start_pos = self.pos

            for i in range(steps):
                if self.stop_motor:
                    raise StopMotorInterrupt()
                else:
                    time.sleep(stepdelay)
                    time.sleep(stepdelay)
                    self.pos += step_increment
                    if verbose:
                        self.logger.debug(f"Steps {i} \ Position: {self.pos}")

        except KeyboardInterrupt:
            self.logger.error("User Keyboard Interrupt")
        except StopMotorInterrupt:
            raise
        except Exception:
            self.logger.error("RpiMotorLib  : Unexpected error:")
            raise

        finally:
            # Print report status
            if verbose:
                self.logger.debug("\nRpiMotorLib, Motor Run finished, Details:.\n")
                self.logger.debug("Motor type = {}".format(self.motor_type))
                self.logger.debug("Direction = {}".format(dir))
                self.logger.debug("Step Type = {}".format(self.steptype))
                self.logger.debug("Number of steps = {}".format(self.pos - start_pos))
                self.logger.debug("Step Delay = {}".format(stepdelay))
                self.logger.debug("Intial delay = {}".format(initdelay))
                self.logger.debug(
                    "Size of turn in degrees = {}".format(self.degree_calc(steps))
                )

    @staticmethod
    def is_locked():
        return False
