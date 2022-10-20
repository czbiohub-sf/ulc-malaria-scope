# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating encoder.
         See encoder module under hardware/real/ for info on actual functionality.
         
"""

from typing import Callable

from ulc_mm_package.hardware.pim522_rotary_encoder import EncoderI2CError


class PIM522RotaryEncoder:
    def __init__(self, callback_func: Callable):
        self.I2C_ADDR = 0x0F  # 0x18 for IO Expander, 0x0F for the encoder breakout
        self.pin_red = 1
        self.pin_green = 7
        self.pin_blue = 2

    def setColor(self, r, g, b):
        pass

    def close(self):
        pass
