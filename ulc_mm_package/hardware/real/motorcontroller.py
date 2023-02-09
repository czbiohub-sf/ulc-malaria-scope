""" DRV8825 - Stepper Motor Controller IC

-- Important Links --
Datasheet:
    https://www.ti.com/lit/ds/symlink/drv8825.pdf

*Adapted from Gavin Lyons' RPiMotorLib repository (https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/RpiMotorLib/RpiMotorLib.py)
"""

import logging
import time
import threading
import pigpio

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
    HomingError,
    StopMotorInterrupt,
    MotorInMotion,
    InvalidMove,
)


MOTOR_LOCK = threading.Lock()


class DRV8825Nema:
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
        steptype="Full",
        lim1=MOTOR_LIMIT_SWITCH1,
        lim2: int = None,
        max_pos: int = None,
        pi: pigpio.pi = None,
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
            (Full, Half, 1/4, 1/8, 1/16) 1/32 for DRV8825 only
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
        self.pos = -int(1e6)
        self.homed = False
        self.stop_motor = False

        # Get step degree based on steptype
        degree_value = {
            "Full": 1.8,
            "Half": 0.9,
            "1/4": 0.45,
            "1/8": 0.225,
            "1/16": 0.1125,
            "1/32": 0.05625,
            "1/64": 0.028125,
            "1/128": 0.0140625,
        }
        self.step_degree = degree_value[steptype]
        self.microstepping = 1.8 / self.step_degree  # 1, 2, 4, 8, 16, 32
        self.dist_per_step_um = (
            self.step_degree / degree_value["Full"] * FULL_STEP_TO_TRAVEL_DIST_UM
        )

        # TODO Calculate the max position allowable based on stepping mode and actual travel distance on the scope
        self.max_pos = (
            int(max_pos) if max_pos != None else int(450 * self.microstepping)
        )

        # Set up GPIO
        self._pi = pi if pi != None else pigpio.pi()
        self._pi.set_mode(self.enable_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.sleep_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.reset_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.fault_pin, pigpio.INPUT)

        self._pi.set_mode(direction_pin, pigpio.OUTPUT)
        self._pi.set_mode(step_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.lim1, pigpio.INPUT)
        self._pi.set_pull_up_down(self.lim1, pigpio.PUD_UP)

        self._pi.write(self.enable_pin, False)
        self._pi.write(self.sleep_pin, True)
        self._pi.write(self.reset_pin, True)

        # Limit switch callbacks
        self._pi.callback(self.lim1, pigpio.FALLING_EDGE, self.motor_stop)

        # Move motor up to ensure it isn't hitting the limit switch
        self._move_rel_steps(
            steps=int(ZERO_OFFSET_STEPS * self.microstepping), dir=Direction.CW
        )

    def close(self):
        self._pi.write(self.sleep_pin, False)
        self._pi.write(self.reset_pin, False)

    def degree_calc(self, steps):
        """calculate and returns size of turn in degree, passed number of steps and steptype"""

        degree_value = steps * self.step_degree
        return degree_value

    def getCurrentPosition(self):
        return self.pos

    def getMinimumTravelDistance_um(self):
        return self.dist_per_step_um

    def isMoveValid(self, dir: Direction, steps: int):
        """If homing has been done, check to see if an attempted move is within the allowable range.

        Parameters
        ----------
        dir : Direction enum
        steps : int
            Number of steps to take
        """

        if self.homed:
            if dir == Direction.CW:
                return self.pos + steps <= self.max_pos
            elif dir == Direction.CCW:
                return self.pos - steps >= 0

        return True

    def homeToLimitSwitches(self):
        """Move to the limit switch and the set the zero position (with an offset).

        If a second limit switch is present, move to that one and set the max position.
        """

        # Adjust the timeout based on the microstepping mode
        homing_timeout = DEFAULT_FULL_STEP_HOMING_TIMEOUT * self.microstepping

        self.logger.info("Waiting for motor to complete homing.")

        # Move the motor until it hits the CCW limit switch
        try:
            self.move_rel(dir=Direction.CCW, steps=1e6, timeout_s=homing_timeout)
        except MotorMoveTimeout:
            raise HomingError(
                f"Motor failed to home in the allotted time ({homing_timeout} seconds)."
            )
        except StopMotorInterrupt:
            # Move slightly until the limit switch is no longer active
            while not self._pi.read(self.lim1):
                self._move_rel_steps(dir=Direction.CW, steps=1)
            self.pos = 0

        if self.lim2 != None:
            # Move to the CW limit switch
            try:
                self.move_rel(dir=Direction.CW, steps=1e6, timeout_s=homing_timeout)
            except MotorMoveTimeout:
                raise HomingError(
                    f"Motor failed to home in the allotted {homing_timeout} seconds."
                )
            except StopMotorInterrupt:
                while not self._pi.read(self.lim1):
                    self._move_rel_steps(dir=Direction.CCW, steps=1)
                self.max_pos = self.pos

        self.logger.info("Done homing motor.")
        self.homed = True

    def motor_stop(self, *args):
        """Stop the motor"""

        self.stop_motor = True

    def _move_rel_steps(self, steps: int, dir=Direction.CCW, stepdelay=0.005):

        # set direction
        self._pi.write(self.direction_pin, dir.value)

        step_increment = 1 if dir else -1
        for i in range(steps):
            self._pi.write(self.step_pin, True)
            time.sleep(stepdelay)
            self._pi.write(self.step_pin, False)
            time.sleep(stepdelay)
            self.pos += step_increment

    @lock_no_block(MOTOR_LOCK, MotorInMotion)
    def move_rel(
        self,
        dir=Direction.CCW,
        steps: int = 200,
        stepdelay=0.005,
        timeout_s: int = 1e6,
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

        # Set direction
        self._pi.write(self.direction_pin, dir.value)

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
                    self._pi.write(self.step_pin, True)
                    time.sleep(stepdelay)
                    self._pi.write(self.step_pin, False)
                    time.sleep(stepdelay)
                    self.pos += step_increment

                    if time.perf_counter() - start_time >= timeout_s:
                        raise MotorMoveTimeout()
                    if verbose:
                        print(f"Steps {i} \ Position: {self.pos}")

        except KeyboardInterrupt:
            raise MotorControllerError("User keyboard interrupt")
        except StopMotorInterrupt:
            raise
        except MotorMoveTimeout:
            raise
        except Exception:
            raise MotorControllerError("Unexpected error in move_rel")

        finally:
            # Cleanup
            self._pi.write(self.step_pin, False)
            self._pi.write(self.direction_pin, False)

            # Print report status
            if verbose:
                print("\nRpiMotorLib, Motor Run finished, Details:.\n")
                print("Motor type = {}".format(self.motor_type))
                print("Direction = {}".format(dir))
                print("Step Type = {}".format(self.steptype))
                print("Number of steps = {}".format(self.pos - start_pos))
                print("Step Delay = {}".format(stepdelay))
                print("Intial delay = {}".format(initdelay))
                print("Size of turn in degrees = {}".format(self.degree_calc(steps)))

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
        self._pi.write(self.direction_pin, dir.value)

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
                    self._pi.write(self.step_pin, True)
                    time.sleep(stepdelay)
                    self._pi.write(self.step_pin, False)
                    time.sleep(stepdelay)
                    self.pos += step_increment
                    if verbose:
                        print(f"Steps {i} \ Position: {self.pos}")

        except KeyboardInterrupt:
            print("User Keyboard Interrupt")
        except StopMotorInterrupt:
            raise
        except Exception:
            print("RpiMotorLib  : Unexpected error:")
            raise

        finally:
            # Cleanup
            self._pi.write(self.step_pin, False)
            self._pi.write(self.direction_pin, False)

            # Print report status
            if verbose:
                print("\nRpiMotorLib, Motor Run finished, Details:.\n")
                print("Motor type = {}".format(self.motor_type))
                print("Direction = {}".format(dir))
                print("Step Type = {}".format(self.steptype))
                print("Number of steps = {}".format(self.pos - start_pos))
                print("Step Delay = {}".format(stepdelay))
                print("Intial delay = {}".format(initdelay))
                print("Size of turn in degrees = {}".format(self.degree_calc(steps)))

    def threaded_move_rel(self, *args, **kwargs):
        if not MOTOR_LOCK.locked():
            threading.Thread(target=self.move_rel, args=args, kwargs=kwargs).start()
        else:
            raise MotorInMotion

    def threaded_move_abs(self, *args, **kwargs):
        if not MOTOR_LOCK.locked():
            threading.Thread(target=self.move_abs, args=args, kwargs=kwargs).start()
        else:
            raise MotorInMotion
