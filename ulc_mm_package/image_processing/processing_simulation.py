# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy functions simulating image processing objects for UI testing.
         See relevant image processing files for more info on methods.
         The class methods and variables are a barebones imitation of the actual functions.

"""

import numpy as np

from ulc_mm_package.image_processing.processing_constants import *
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule, SyringeDirection, PressureLeak

# ------------------------------autobrightness.py------------------------------

class AutobrightnessError(Exception):
    """Base class for catching Autobrightness errors."""
    
    def __init__(self, msg: str):
        super().__init__(f"{msg}")

class Autobrightness():
    def __init__(self, led: LED_TPS5420TDDCT, target_pixel_val: int=TOP_PERC_TARGET_VAL, step_size_perc: float=0.01):
        self.prev_brightness_enum = None
        self.target_pixel_val = target_pixel_val
        self.led = led
        self.step_size_perc = step_size_perc
        self.default_step_size_perc = step_size_perc
        self.timeout_steps = 100
        self.step_counter = 0
    
    def runAutobrightness(self, img: np.ndarray):
        pass

    def reset(self):
        pass

# ------------------------------flow_control.py------------------------------

class FlowController:
    def __init__(self, pneumatic_module: PneumaticModule, h: int=600, w: int=800, window_size: int=WINDOW_SIZE):
        self.window_size = window_size
        self.pneumatic_module = pneumatic_module
        self.flowrates = np.zeros(self.window_size)
        # self.fre = FlowRateEstimator(h, w, num_image_pairs=NUM_IMAGE_PAIRS)

        self._idx = 0
        self.target_flowrate: float = None
        self.curr_flowrate: float = None

    def controlFlow(self, img: np.ndarray):
        pass