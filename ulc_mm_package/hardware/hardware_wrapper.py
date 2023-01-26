# -*- coding: utf-8 -*-
"""

@author: mwlkhoo

Purpose: Decorator for any hardware with a simulated and real object.
         This decorator decides whether simulated or real hardware objects
         should be passed to the hardware wrapper.

Usage:   Define a new hardware class as

            @hardware
            def HardwareClass():
                pass

         There should be a real and simulated version of this hardware under hardware/real
         and hardware/sim, respectively. Ensure filenames and class names are identical.

         Note that all exceptions should be declared in the hardware wrapper file. The exception
         can then be imported into real or simulated hardware files as necessary.

         Locks should live in the real hardware file only.
"""

import inspect

from importlib import import_module
from os.path import basename

from ulc_mm_package.scope_constants import SIMULATION


PKG_PATH = "ulc_mm_package.hardware."


# TODO should the HardwareWrapper wrap abstract base classes that are inherited by sim and real?

def hardware(cls):
    class HardwareWrapper(cls):
        def __new__(cls, *args, **kwargs):

            parent = inspect.getmro(cls)[1]

            mod_name = parent.__module__.split(".")[-1]
            obj_name = parent.__name__

            if SIMULATION:
                mod = import_module(PKG_PATH + "sim." + mod_name)
            else:
                mod = import_module(PKG_PATH + "real." + mod_name)

            obj = getattr(mod, obj_name)
            return obj(*args, **kwargs)

    return HardwareWrapper
