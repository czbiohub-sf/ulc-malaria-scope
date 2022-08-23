# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy functions simulating hardware objects for UI testing.
         See relevant hardware object files for more info on methods.
         The class methods and variables are a barebones imitation of the actual hardware.

"""

import enum
import cv2
import numpy as np
import scipy

from os import path
from py_cameras import PyCamera
from ulc_mm_package.hardware.hardware_constants import *
from typing import Callable
from time import sleep

# Pressure control constants
INVALID_READ_FLAG = -1
DEFAULT_AFC_DELAY_S = 10
FASTER_FEEDBACK_DELAY_S = 3

# ------------------------------motorcontroller.py------------------------------



# ------------------------------led_driver_tps54201ddct.py------------------------------



# ------------------------------pim522_rotary_encoder.py------------------------------

# ------------------------------pressure_control.py------------------------------

class PneumaticModuleError(Exception):
    pass

class PressureLeak(PneumaticModuleError):
    def __init__(self):
        super().__init__("Pressure leak detected.")

class SyringeDirection(enum.Enum):
    """Enum for the direction of the syringe."""
    UP = 1
    DOWN = -1

class PneumaticModule():
    def __init__(self, servo_pin: int=SERVO_PWM_PIN):
        self.servo_pin = servo_pin
        self.min_step_size = 10
        self.min_duty_cycle = 1600
        self.max_duty_cycle = 2200
        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle
        self.polling_time_s = 3
        self.prev_poll_time_s = 0
        self.prev_pressure = 0
        self.io_error_counter = 0
        self.prev_time_s = 0
        self.control_delay_s = 0.2
        self.curr_pressure = self.prev_pressure

        # Active flow control variables
        self.flowrate_target = 0
        self.flow_rate_y = 0
        self.prev_afc_time_s = 0
        self.afc_delay_s = DEFAULT_AFC_DELAY_S

    def getPressure(self, apc_on: bool=False):
        return self.curr_pressure

    def getCurrentDutyCycle(self):
        return self.duty_cycle

    def getMaxDutyCycle(self):
        return self.max_duty_cycle

    def getMinDutyCycle(self):
        return self.min_duty_cycle

    def increaseDutyCycle(self):
        if self.duty_cycle <= self.max_duty_cycle - self.min_step_size:
            self.duty_cycle += self.min_step_size
            # sleep(0.01)

    def decreaseDutyCycle(self):
        if self.duty_cycle >= self.min_duty_cycle + self.min_step_size:
            self.duty_cycle -= self.min_step_size
            # sleep(0.01)

    def setDutyCycle(self, duty_cycle: int):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle <= duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
            else:
                while self.duty_cycle >= duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()

    def threadedDecreaseDutyCycle(self, *args, **kwargs):
        self.decreaseDutyCycle()

    def threadedIncreaseDutyCycle(self, *args, **kwargs):
        self.increaseDutyCycle()

    def threadedSetDutyCycle(self, *args, **kwargs):
        self.setDutyCycle()

    def close(self):
        self.setDutyCycle(self.max_duty_cycle)

    def holdPressure(target_pressure):
        pass


# ------------------------------fan.py------------------------------

class Fan():
    def __init__(self, fan_pin: int=FAN_GPIO):
        pass
    
    def turn_on(self, pin):
        pass
    
    def turn_off(self, pin):
        pass
    
    def setup_pin(self, fan_pin):
        pass

    def turn_on_all(self):
        pass

    def turn_off_all(self):
        pass