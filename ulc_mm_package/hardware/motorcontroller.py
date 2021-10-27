""" DRV8825 - Stepper Motor Controller IC

-- Important Links -- 
Datasheet:
    https://www.ti.com/lit/ds/symlink/drv8825.pdf
    
*Taken and adpated from Gavin Lyons' RPiMotorLib repository (https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/RpiMotorLib/RpiMotorLib.py)
"""

from math import pi as PI
import sys
import enum
import time
import pigpio

from ulc_mm_package.hardware.encoder import Encoder
from ulc_mm_package.hardware.hardware_constants import *

# ==================== Custom errors ===============================
class StopMotorInterrupt(Exception):
    """ Stop the motor """
    pass

class InvalidMove(Exception):
    pass

# ==================== Convenience enum for readability ===============================
class Direction(enum.Enum):
    CW = True
    CCW = False

class DRV88258Nema():
    """ Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """

    def __init__(
                    self, 
                    direction_pin=DIR_PIN, 
                    step_pin=STEP_PIN, 
                    motor_type="DRV8825", 
                    steptype="Full", 
                    lim1=LIMIT_SWITCH1, 
                    lim2: int=None, 
                    max_pos: int=None, 
                    encoder_A=ROT_A_PIN, 
                    encoder_B=ROT_B_PIN, 
                    pi: pigpio.pi=None, 
                    step_distance_ratio: float = SHAFT_TRAVEL_RATIO,
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
        encoder_a : int
            Rotary encoder pin A
        encoder_b : int 
            Rotary encoder pin B
        pi : pigpio.pi()
            Optional parameter to pass an existing pigpio.pi() object. This would be passed in for cases where you may want two or more hardware objects to 
            both use the same callback thread
        """
        self.motor_type = motor_type
        self.direction_pin = direction_pin
        self.step_pin = step_pin
        self.lim1 = lim1
        self.lim2 = lim2
        self.steptype = steptype
        self.encoder = Encoder(encoder_A, encoder_B)
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
        self.dist_per_step_um = (self.step_degree/360 * PI*SHAFT_DIAM_UM) * step_distance_ratio

        # TODO Calculate the max position allowable based on stepping mode and actual travel distance on the scope
        self.max_pos = max_pos if max_pos != None else 1e6

        # Set up GPIO
        self._pi = pi if pi != None else pigpio.pi()
        self._pi.set_mode(direction_pin, pigpio.OUTPUT)
        self._pi.set_mode(STEP_PIN, pigpio.OUTPUT)
        self._pi.set_mode(self.lim1, pigpio.INPUT)

        # Limit switch callbacks
        self._pi.callback(self.lim1, pigpio.RISING, callback=self.motor_stop)

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
                return self.encoder.getCount() + steps <= self.max_pos
            elif dir == Direction.CCW:
                return self.encoder.getCount() - steps >= 0

        return True

    def homeToLimitSwitches(self):
        """Move to the limit switch and the set the zero position (with an offset).
        
        If a second limit switch is present, move to that one and set the max position.
        """

        # Move the motor until it hits the CCW limit switch
        self.motor_go(dir=Direction.CCW, steps=1e6)

        # Add slight offset to zero position
        self.motor_go(dir=Direction.CW, steps=ZERO_OFFSET_STEPS)
        self.encoder.resetCount()

        if self.lim2 != None:
            # Move to the CW limit switch
            self.motor_go(dir=Direction.CW, steps=1e6)
            self.motor_go(dir=Direction.CCW, steps=ZERO_OFFSET_STEPS)

            # Set limit
            self.max_pos = self.encoder.getCount()
            
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
        step_increment = 1 if dir else -1

        # set direction
        self._pi.write(self.direction_pin, dir)

        if self.homed:
            if not self.isMoveValid(dir, steps):
                direction = "CW (+)" if dir else "CCW (-)"
                raise InvalidMove(f"""
                =======INVALID MOVE, OUT OF RANGE=======
                Current position: {self.encoder.getCount()}\n
                Attempted direction: {direction}\n
                Attempted steps: {steps}\n
                Allowable range: 0 <= steps <= {self.max_pos}\n
                Attempted move would result in: {self.encoder.getCount() + step_increment*steps}
                """)

        try:
            time.sleep(initdelay)
            start_pos = self.encoder.getCount()
            curr_pos = self.encoder.getCount()
            end_pos = self.encoder.getCount() + step_increment*steps
            while (step_increment == 1 and curr_pos < end_pos) or (step_increment == -1 and curr_pos > end_pos):
                if self.stop_motor:
                    # Limit switch triggered
                    return
                else:
                    self._pi.write(self.step_pin, True)
                    time.sleep(stepdelay)
                    self._pi.write(self.step_pin, False)
                    time.sleep(stepdelay)
                    curr_pos = self.encoder.getCount()
                    if verbose:
                        print(f"Steps {curr_pos-start_pos}")

        except KeyboardInterrupt:
            print("User Keyboard Interrupt : RpiMotorLib:")
        except StopMotorInterrupt:
            print("Stop Motor Interrupt : RpiMotorLib: ")
        except Exception as motor_error:
            print(sys.exc_info()[0])
            print(motor_error)
            print("RpiMotorLib  : Unexpected error:")

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
                print("Number of steps = {}".format(self.encoder.getCount() - start_pos))
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
        if not allow_rounding:
            raise InvalidMove(f"\
                    Minimum step distance: {self.dist_per_step_um}\n \
                    Attempted move: {distance_um}\n \
                    Warning: Move will be off by {distance_um % self.dist_per_step_um}")

        steps = int(distance_um / self.dist_per_step_um)
        self.motor_go(dir=dir, steps=steps)

    

if __name__ == "__main__":
    print("Instantiating motor...")
    motor = DRV88258Nema(steptype="Full") # Instantiate with all other defaults
    print("Successfully instantiated.")

    print("Beginning homing...")
    motor.homeToLimitSwitches()
    print("Homing complete.")

