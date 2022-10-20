# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating fan.
         See fan module under hardware/real/ for info on actual functionality.
         
"""

from ulc_mm_package.hardware.hardware_constants import FAN_GPIO


class Fan:
    def __init__(self, fan_pin: int = FAN_GPIO):
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
