# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy functions simulating hardware objects for UI testing.
         See relevant hardware object files for more info on methods.
         The class methods and variables are a barebones imitation of the actual hardware.

"""

from time import sleep
from ulc_mm_package.hardware.hardware_constants import (
    SERVO_PWM_PIN,
    INVALID_READ_FLAG,
    DEFAULT_AFC_DELAY_S,
)
from ulc_mm_package.hardware.pneumatic_module import (
    PneumaticModuleError,
    PressureLeak,
    SyringeDirection,
)

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