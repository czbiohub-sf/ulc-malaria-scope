from typing import Callable

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