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

# ========================== IMPORTS ======================
# Import the system modules needed to run rpiMotorlib.py
import sys
import enum
import time
import RPi.GPIO as GPIO

from hardware_constants import *

# ==================== CLASS SECTION ===============================

class StopMotorInterrupt(Exception):
    """ Stop the motor """
    pass

class InvalidMove(Exception):
    """ Motor move not in range """
    pass

class Direction(enum.Enum):
    CW = True
    CCW = False

class DRV88258Nema():
    """ Class to control a Nema bi-polar stepper motor for a DRV8825.
    Default pin values set to the pins laid out on the malaria scope PCB schematic, and GPIO microstepping selection disabled."""
    def __init__(self, direction_pin=DIR_PIN, step_pin=STEP_PIN, motor_type="DRV8825", steptype="Full", 
                    lim1=LIMIT_SWITCH1, lim2=LIMIT_SWITCH2):
        """ class init method 3 inputs
        (1) direction type=int , help=GPIO pin connected to DIR pin of IC
        (2) step_pin type=int , help=GPIO pin connected to STEP of IC
        (3) motor_type type=string, help=Type of motor two options: A4988 or DRV8825
        (4) steptype, type=string , default=Full help= type of drive to step motor 5 options
            (Full, Half, 1/4, 1/8, 1/16) 1/32 for DRV8825 only
        (5) lim1, type=int, help=Limit switch 1 GPIO pin
        (6) lim2, type=int, help=Limit switch 2 GPIO pin
        """
        self.motor_type = motor_type
        self.direction_pin = direction_pin
        self.step_pin = step_pin
        self.lim1 = lim1
        self.lim2 = lim2
        self.steptype = steptype
        self.pos = 0
        self.homed = False
        self.stop_motor = False

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Limit switch callbacks
        GPIO.add_event_detect(self.lim1, GPIO.RISING, callback=self.motor_stop, bouncetime=200)
        GPIO.add_event_detect(self.lim2, GPIO.RISING, callback=self.motor_stop, bouncetime=200)

    def isMoveValid(self, dir, steps):
        """If homing has been done, check to see if a motion is within the allowable range."""

        if self.homed:
            if dir == Direction.CW:
                return self.pos + steps <= self.max_pos
            elif dir == Direction.CCW:
                return self.pos - steps >= 0

        return True

    def homeToLimitSwitches(self):
        """Move to both limit switches and the set the zero and max position"""

        # Move the motor until it hits the CCW limit switch
        self.motor_go(clockwise=Direction.CCW, steps=1e6)

        # Add slight offset to zero position
        self.motor_go(clockwise=Direction.CW, steps=ZERO_OFFSET_STEPS)
        self.pos = 0

        # Move to the CW limit switch
        self.motor_go(clockwise=Direction.CW, steps=1e6)
        self.motor_go(clockwise=Direction.CCW, steps=ZERO_OFFSET_STEPS)

        # Set limit
        self.max_pos = self.pos
        self.homed = True

    def motor_stop(self):
        """ Stop the motor """
        self.stop_motor = True

    def motor_go(self, clockwise=Direction.CCW,
                 steps=200, stepdelay=.005, verbose=False, initdelay=.05):
        """ motor_go,  moves stepper motor based on 6 inputs

         (1) clockwise, type=bool default=False
         help="True - clockwise, False - CCW"
         (2) steps, type=int, default=200, help=Number of steps sequence's
         to execute. Default is one revolution , 200 in Full mode.
         (3) stepdelay, type=float, default=0.05, help=Time to wait
         (in seconds) between steps.
         (4) verbose, type=bool  type=bool default=False
         help="Write pin actions",
         (5) initdelay, type=float, default=1mS, help= Intial delay after
         GPIO pins initialized but before motor is moved.

        """
        self.stop_motor = False
        step_increment = 1 if clockwise else -1

        # setup GPIO
        GPIO.setup(self.direction_pin, GPIO.OUT)
        GPIO.setup(self.step_pin, GPIO.OUT)
        GPIO.output(self.direction_pin, clockwise)

        if self.homed:
            if not self.isMoveValid(clockwise, steps):
                direction = "CW (+)" if clockwise else "CCW (-)"
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

            for i in range(steps):
                if self.stop_motor:
                    # Limit switch triggered, return the number of steps taken
                    return i
                else:
                    GPIO.output(self.step_pin, True)
                    time.sleep(stepdelay)
                    GPIO.output(self.step_pin, False)
                    time.sleep(stepdelay)
                    self.pos += step_increment
                    if verbose:
                        print("Steps count {}".format(i+1), end="\r", flush=True)

        except KeyboardInterrupt:
            print("User Keyboard Interrupt : RpiMotorLib:")
        except StopMotorInterrupt:
            print("Stop Motor Interrupt : RpiMotorLib: ")
        except Exception as motor_error:
            print(sys.exc_info()[0])
            print(motor_error)
            print("RpiMotorLib  : Unexpected error:")
        else:
            # print report status
            if verbose:
                print("\nRpiMotorLib, Motor Run finished, Details:.\n")
                print("Motor type = {}".format(self.motor_type))
                print("Clockwise = {}".format(clockwise))
                print("Step Type = {}".format(self.steptype))
                print("Number of steps = {}".format(steps))
                print("Step Delay = {}".format(stepdelay))
                print("Intial delay = {}".format(initdelay))
                print("Size of turn in degrees = {}"
                      .format(degree_calc(steps, self.steptype)))
        finally:
            # cleanup
            GPIO.output(self.step_pin, False)
            GPIO.output(self.direction_pin, False)

def degree_calc(steps, steptype):
    """ calculate and returns size of turn in degree
    , passed number of steps and steptype"""
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

