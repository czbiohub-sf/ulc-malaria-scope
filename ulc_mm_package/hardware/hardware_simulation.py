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


# ------------------------------motorcontroller.py------------------------------



# ------------------------------led_driver_tps54201ddct.py------------------------------



# ------------------------------pim522_rotary_encoder.py------------------------------

# ------------------------------pressure_control.py------------------------------




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