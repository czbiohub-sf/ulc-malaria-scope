# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating LED.
         See LED module under hardware/real/ for info on actual functionality.
         
"""

from ulc_mm_package.hardware.hardware_constants import LED_FREQ, LED_PWM_PIN
from ulc_mm_package.hardware.led_driver_tps54201ddct import LEDError


class LED_TPS5420TDDCT():
    def __init__(self, pwm_pin: int=LED_PWM_PIN):
        self._isOn = False
        self.pwm_pin = pwm_pin
        self.pwm_freq = int(LED_FREQ)
        self.pwm_duty_cycle = 10

    def close(self):
        self.pwm_duty_cycle = 0

    def _convertPWMValToDutyCyclePerc(self, pwm_val: int) -> float:
        return pwm_val / 1e6

    def setDutyCycle(self, duty_cycle_perc: float):
        self.pwm_duty_cycle = self._convertDutyCyclePercentToPWMVal(duty_cycle_perc)

    def _convertDutyCyclePercentToPWMVal(self, duty_cycle_percentage: float) -> int:
        return int(1e6*duty_cycle_percentage)

    def turnOn(self):
        self._isOn = True

    def turnOff(self):
        self.setDutyCycle(0)
        self._isOn = False
