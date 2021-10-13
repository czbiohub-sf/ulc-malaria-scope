#!/usr/bin/env python3
"""Taken and adpated from Gavin Lyons' RPiMotorLib repository (https://github.com/gavinlyonsrepo/RpiMotorLib/blob/master/RpiMotorLib/RpiMotorLib.py)"""
# ========================= HEADER ===================================
# title             :rpiMotorlib.py
# description       :A python 3 library for various motors
# and servos to connect to a raspberry pi
# This file is for stepper motor tested on
# Bipolar Nema Stepper motor DRV8825 Driver class
# Main author       :Gavin Lyons
# Version           :See changelog at url
# url               :https://github.com/gavinlyonsrepo/RpiMotorLib
# mail              :glyons66@hotmail.com
# python_version    :3.5.3

# Adapted by:       Ilakkiyan Jeyakumar
# Date:             2021-Oct-06

import sys
import enum
import time
import pigpio

from encoder import Encoder
from hardware_constants import *

# ==================== Custom errors ===============================

class StopMotorInterrupt(Exception):
    """ Stop the motor """
    pass

class InvalidMove(Exception):
    """ Motor move not in range """
    pass

# ==================== Convenience enum for readability ===============================
class Direction(enum.Enum):
    CW = True
    CCW = False

# ==================== Main class ===============================
class DRV88258Nema():
    """ Class to control a Nema bi-polar stepper motor for a DRV8825.

    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled.
    """

    def __init__(self, direction_pin=DIR_PIN, step_pin=STEP_PIN, motor_type="DRV8825", steptype="Full", 
                    lim1=LIMIT_SWITCH1, lim2=LIMIT_SWITCH2, encoder_A=ROT_A_PIN, encoder_B=ROT_B_PIN):
        """Class init method 3 inputs

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
            Limit switch 2 GPIO pin
        encoder_a : int
            Rotary encoder pin A
        encoder_b : int 
            Rotary encoder pin B
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

        # Set up GPIO
        self._pi = pigpio.pi()
        self._pi.set_mode(direction_pin, pigpio.OUTPUT)
        self._pi.set_mode(STEP_PIN, pigpio.OUTPUT)
        self._pi.set_mode(self.lim1, pigpio.INPUT)
        self._pi.set_mode(self.lim2, pigpio.INPUT)

        # Limit switch callbacks
        self._pi.callback(self.lim1, pigpio.RISING, callback=self.motor_stop)
        self._pi.callback(self.lim2, pigpio.RISING, callback=self.motor_stop)

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
        """Move to both limit switches and the set the zero and max position"""

        # Move the motor until it hits the CCW limit switch
        self.motor_go(clockwise=Direction.CCW, steps=1e6)

        # Add slight offset to zero position
        self.motor_go(clockwise=Direction.CW, steps=ZERO_OFFSET_STEPS)
        self.encoder.resetCount()

        # Move to the CW limit switch
        self.motor_go(clockwise=Direction.CW, steps=1e6)
        self.motor_go(clockwise=Direction.CCW, steps=ZERO_OFFSET_STEPS)

        # Set limit
        self.max_pos = self.encoder.getCount()
        self.homed = True

    def motor_stop(self, *args):
        """ Stop the motor """

        self.stop_motor = True

    def motor_go(self, clockwise=Direction.CCW,
                 steps=200, stepdelay=.005, verbose=False, initdelay=.05):
        """motor_go,  moves stepper motor based on 6 inputs

        Parameters
        ----------
        clockwise : Direction enum
        steps : int
            Number of steps Default is 200 (one revolution in Full mode)
        stepdelay : float 
            Time to wait (in seconds) between steps
        verbose : bool
        initdelay : float
            Intial delay after GPIO pins initialized but before motor is moved
        """

        self.stop_motor = False
        step_increment = 1 if clockwise else -1

        # set direction
        self._pi.write(self.direction_pin, clockwise)

        if self.homed:
            if not self.isMoveValid(clockwise, steps):
                direction = "CW (+)" if clockwise else "CCW (-)"
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
            end_pos = self.encoder.getCount() + step_increment*steps
            while (step_increment == 1 and self.encoder.getCount() < end_pos) or (step_increment == -1 and self.encoder.getCount() > end_pos):
                if self.stop_motor:
                    # Limit switch triggered
                    return
                else:
                    self._pi.write(self.step_pin, True)
                    time.sleep(stepdelay)
                    self._pi.write(self.step_pin, False)
                    time.sleep(stepdelay)
                    if verbose:
                        print("Steps count {}".format(self.encoder.getCount()-start_pos), flush=True)

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
                print("Clockwise = {}".format(clockwise))
                print("Step Type = {}".format(self.steptype))
                print("Number of steps = {}".format(self.encoder.getCount() - start_pos))
                print("Step Delay = {}".format(stepdelay))
                print("Intial delay = {}".format(initdelay))
                print("Size of turn in degrees = {}"
                      .format(degree_calc(steps, self.steptype)))

def degree_calc(steps, steptype):
    """calculate and returns size of turn in degree, passed number of steps and steptype"""
    
    degree_value = {'Full': 1.8,
                    'Half': 0.9,
                    '1/4': .45,
                    '1/8': .225,
                    '1/16': 0.1125,
                    '1/32': 0.05625,
                    '1/64': 0.028125,
                    '1/128': 0.0140625}
    degree_value = (steps*degree_value[steptype])
    return degree_value


if __name__ == "__main__":
    print("Instantiating motor...")
    motor = DRV88258Nema(steptype="Full") # Instantiate with all other defaults
    print("Successfully instantiated.")

    print("Beginning homing...")
    motor.homeToLimitSwitches()
    print("Homing complete.")

