# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Dummy hardware object simulating fan.
         See fan module under hardware/real/ for info on actual functionality.

"""

from ulc_mm_package.hardware.fan import FanBase
from ulc_mm_package.hardware.hardware_constants import FAN_GPIO


class Fan(FanBase):
    ...
