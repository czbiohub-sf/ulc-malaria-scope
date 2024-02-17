""" PIM522 Pimoroni RGB Rotary Encoder w/ Nuvoton microcontroller

See encoder module under hardware/real/ for more info.

"""

from typing import Callable

from ulc_mm_package.hardware.hardware_wrapper import hardware


class EncoderI2CError(Exception):
    """Base class for catching encoder errors."""


@hardware
class PIM522RotaryEncoder:
    def __init__(self, callback_func: Callable):
        """A convenience wrapper on top of the Pimoroni PIM522 library.

        Parameters
        ----------
        callback_func: A callbable function.
            This function will be passed either a positive or negative number indicating the number of steps taken by the encoder
            since the last read. When the encoder is rotated at a slow/moderate speed, this will usually always be +1/-1.
            If the encoder is spun quickly however, this number may be larger.
        """

    def close(self): ...

    def disableInterrupt(self): ...

    def enableInterrupt(self): ...

    def setInterruptCallback(self, callback_func: Callable): ...

    def getCount(self): ...

    def setColor(self, r, g, b): ...
