from importlib import import_module
from os.path import basename

import inspect

from ulc_mm_package.QtGUI.gui_constants import SIMULATION

PKG_PATH = 'ulc_mm_package.hardware.'

def hardware(cls):
    class HardwareWrapper(cls):
        def __new__(cls, *args, **kwargs):
            
            parent = inspect.getmro(cls)[1]

            mod_name = parent.__module__.split('.')[-1]
            obj_name = parent.__name__

            if SIMULATION:
                mod = import_module(PKG_PATH + 'sim.' + mod_name)
                # from ulc_mm_package.hardware.sim.camera import BaslerCamera
            else:
                mod = import_module(PKG_PATH + 'real.' + mod_name)
                # from ulc_mm_package.hardware.real.camera import BaslerCamera
            # return BaslerCamera()
            obj = getattr(mod, obj_name)
            return obj(*args, **kwargs)
            
    return HardwareWrapper
