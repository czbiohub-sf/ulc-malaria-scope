# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating LED.
         See LED module under hardware/real/ for info on actual functionality.

"""

from time import sleep
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT_Base
from ulc_mm_package.hardware.hardware_constants import (
    LED_PWM_PIN,
    ANALOG_DIM_MODE_DUTYCYCLE,
    LED_FREQ,
)
from ulc_mm_package.hardware.hardware_constants import LED_FREQ, LED_PWM_PIN
from ulc_mm_package.hardware.dtoverlay_pwm import PWM_CHANNEL

from ulc_mm_package.hardware.sim.dtoverlay_pwm import dtoverlay_PWM


class LED_TPS5420TDDCT(LED_TPS5420TDDCT_Base):
    def __init__(self, pwm_pin: int = LED_PWM_PIN):
        self._isOn = False
        self.pwm_freq = int(LED_FREQ)
        self.pwm_duty_cycle = ANALOG_DIM_MODE_DUTYCYCLE
        self.pwm = dtoverlay_PWM(PWM_CHANNEL.PWM2)

        # Set the dimming mode (see datasheet, page 17)
        self.pwm.setFreq(50000)
        self.pwm.setDutyCycle(ANALOG_DIM_MODE_DUTYCYCLE)
        sleep(0.0005)
        self.pwm.setFreq(self.pwm_freq)
        self.pwm.setDutyCycle(0)
