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


if __name__ == "__main__":

    def hi(dir: int):
        print(f"Hi: {dir}")

    def bye(dir: int):
        print(f"Bye: {dir}")

    enc = PIM522RotaryEncoder(callback_func=hi)
    try:
        from time import sleep

        while True:
            if enc.getCount() > 300:
                enc.setColor(255, 0, 0)
            elif enc.getCount() > 200:
                enc.setColor(0, 255, 0)
            elif enc.getCount() > 0:
                enc.setColor(0, 0, 255)
            sleep(1 / 30)
    except KeyboardInterrupt:
        enc.setColor(0, 0, 0)
        quit()
