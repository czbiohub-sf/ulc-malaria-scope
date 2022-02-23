""" DRV8825 - Stepper Motor Controller IC

-- Important Links -- 
Datasheet:
    https://www.ti.com/lit/ds/symlink/drv8825.pdf
    
*Taken and adpated from Gavin Lyons' RPiMotorLib repository (https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/RpiMotorLib/RpiMotorLib.py)
"""

import sys
import enum
import time
import pigpio

from ulc_mm_package.hardware.hardware_constants import *

# ==================== Custom errors ===============================

class MotorControllerError(Exception):
    """ Base class for catching all motor controller related errors. """
    pass

class HomingError(MotorControllerError):
    """ Error raised if an issue occurs during the homing procedure. """
    pass

class StopMotorInterrupt(MotorControllerError):
    """ Stop the motor. """
    pass

class InvalidMove(MotorControllerError):
    """Error raised if an invalid move is attempted."""
    pass

# ==================== Convenience enum for readability ===============================
class Direction(enum.Enum):
    CW = True
    CCW = False

class DRV8825Nema():
    """ Class to control a Nema bi-polar stepper motor for a DRV8825.

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
                    lim2: int=None,
                    max_pos: int=None,
                    pi: pigpio.pi=None, 
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
        self.pos = 0
        self.homed = False
        self.stop_motor = False

        # Get step degree based on steptype
        degree_value = {'Full': 1.8,
                        'Half': 0.9,
                        '1/4': .45,
                        '1/8': .225,
                        '1/16': 0.1125,
                        '1/32': 0.05625,
                        '1/64': 0.028125,
                        '1/128': 0.0140625}
        self.step_degree = degree_value[steptype]
        self.dist_per_step_um = self.step_degree / degree_value['Full'] * FULL_STEP_TO_TRAVEL_DIST_UM

        # TODO Calculate the max position allowable based on stepping mode and actual travel distance on the scope
        self.max_pos = max_pos if max_pos != None else 1e6

        # Set up GPIO
        self._pi = pi if pi != None else pigpio.pi()
        self._pi.set_mode(self.enable_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.sleep_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.reset_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.fault_pin, pigpio.INPUT)

        self._pi.set_mode(direction_pin, pigpio.OUTPUT)
        self._pi.set_mode(step_pin, pigpio.OUTPUT)
        self._pi.set_mode(self.lim1, pigpio.INPUT)

        self._pi.write(self.enable_pin, False)
        self._pi.write(self.sleep_pin, True)
        self._pi.write(self.reset_pin, True)

        # Limit switch callbacks
        self._pi.callback(self.lim1, pigpio.RISING_EDGE, self.motor_stop)

    def degree_calc(self, steps):
        """calculate and returns size of turn in degree, passed number of steps and steptype"""
    
        degree_value = steps * self.step_degree
        return degree_value

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

        try:
            # Move the motor until it hits the CCW limit switch
            try:
                print("CCW")
                self.motor_go(dir=Direction.CCW, steps=1e6)
            except StopMotorInterrupt:
                # Add slight offset to zero position
                self.motor_go(dir=Direction.CW, steps=ZERO_OFFSET_STEPS)
                self.pos = 0

            if self.lim2 != None:
                # Move to the CW limit switch
                try:
                    self.motor_go(dir=Direction.CW, steps=1e6)
                except StopMotorInterrupt:
                    self.motor_go(dir=Direction.CCW, steps=ZERO_OFFSET_STEPS)
                    self.max_pos = self.pos
        except:
            raise HomingError()
            
        self.homed = True

    def motor_stop(self, *args):
        """ Stop the motor """

        self.stop_motor = True

    def motor_go(self, dir=Direction.CCW,
                 steps=200, stepdelay=.005, verbose=False, initdelay=.05):
        """motor_go,  moves stepper motor based on 6 inputs

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

        dir = dir.value
        self.stop_motor = False
        steps = int(steps)
        step_increment = 1 if dir else -1

        # set direction
        self._pi.write(self.direction_pin, dir)

        if self.homed:
            if not self.isMoveValid(dir, steps):
                direction = "CW (+)" if dir else "CCW (-)"
                raise InvalidMove(f"""
                =======INVALID MOVE, OUT OF RANGE=======
                Current position: {self.pos}\n
                Attempted direction: {direction}\n
                Attempted steps: {steps}\n
                Allowable range: 0 <= steps <= {self.max_pos}\n
                Attempted move would result in: {self.pos + step_increment*steps}
                """)

        try:
            time.sleep(initdelay)
            start_pos = self.pos

            for i in range(steps):
                if self.stop_motor:
                    raise StopMotorInterrupt("Limit switch hit.")
                else:
                    print("Running ", self.step_pin)
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
            print("Stop Motor Interrupt")
        except Exception:
            print("RpiMotorLib  : Unexpected error:")
            raise

        finally:
            # cleanup
            self._pi.write(self.step_pin, False)
            self._pi.write(self.direction_pin, False)

            # print report status
            if verbose:
                print("\nRpiMotorLib, Motor Run finished, Details:.\n")
                print("Motor type = {}".format(self.motor_type))
                print("Direction = {}".format(dir))
                print("Step Type = {}".format(self.steptype))
                print("Number of steps = {}".format(self.pos - start_pos))
                print("Step Delay = {}".format(stepdelay))
                print("Intial delay = {}".format(initdelay))
                print("Size of turn in degrees = {}"
                      .format(self.degree_calc(steps)))

    def move_distance(self, distance_um: float, dir: Direction, allow_rounding: bool=False):
        """Convert a distance to a stepper motor move.

        Parameters
        ----------
        distance_um : float
            Desired travel distance to move (i.e assembly motion)
        dir : Direction enum
        allow_rounding : bool=False
            Toggle whether to raise an error when the attempted move is not a multiple of the step distance
        """
        if (not allow_rounding and distance_um % self.dist_per_step_um != 0) or distance_um > self.dist_per_step_um:
            raise InvalidMove(f"\
                    Minimum step distance: {self.dist_per_step_um}\n \
                    Attempted move: {distance_um}\n \
                    Warning: Move will be off by {distance_um % self.dist_per_step_um}")

        steps = int(distance_um / self.dist_per_step_um)
        self.motor_go(dir=dir, steps=steps)
    

if __name__ == "__main__":
    print("Instantiating motor...")
    motor = DRV8825Nema(steptype="Full") # Instantiate with all other defaults
    print("Successfully instantiated.")

    print("Beginning homing...")
    motor.homeToLimitSwitches()
    print("Homing complete.")

