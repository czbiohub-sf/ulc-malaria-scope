""" PIM522 Pimoroni RGB Rotary Encoder w/ Nuvoton microcontroller

-- Important Links --
Pimoroni Product Page:
    https://shop.pimoroni.com/products/rgb-encoder-breakout
Python Library:
    https://github.com/pimoroni/ioe-python
Encoder Dimensions:
    https://cdn.shopify.com/s/files/1/0174/1800/files/EC12PVF-D-15F-24-24C-03-6H.pdf?v=1601306386
"""

import ioexpander as io

from time import sleep
from typing import Callable

from ulc_mm_package.hardware.hardware_constants import (
    ROT_A_PIN,
    ROT_B_PIN,
    ROT_C_PIN,
    ROT_INTERRUPT_PIN,
)
from ulc_mm_package.hardware.pim522_rotary_encoder import EncoderI2CError


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
        self.I2C_ADDR = 0x0F  # 0x18 for IO Expander, 0x0F for the encoder breakout

        self.pin_red = 1
        self.pin_green = 7
        self.pin_blue = 2

        POT_ENC_A = ROT_A_PIN
        POT_ENC_B = ROT_B_PIN
        POT_ENC_C = ROT_C_PIN

        BRIGHTNESS = (
            1  # Effectively the maximum fraction of the period that the LED will be on
        )
        PERIOD = int(
            255 / BRIGHTNESS
        )  # Add a period large enough to get 0-255 steps at the desired brightness

        try:
            ioe = io.IOE(i2c_addr=self.I2C_ADDR, interrupt_pin=ROT_INTERRUPT_PIN)

            # Swap the interrupt pin for the Rotary Encoder breakout
            if self.I2C_ADDR == 0x0F:
                ioe.enable_interrupt_out(pin_swap=True)

            ioe.setup_rotary_encoder(1, POT_ENC_A, POT_ENC_B, POT_ENC_C)

            ioe.set_pwm_period(PERIOD)
            ioe.set_pwm_control(divider=2)  # PWM as fast as we can to avoid LED flicker

            ioe.set_mode(self.pin_red, io.PWM, invert=True)
            ioe.set_mode(self.pin_green, io.PWM, invert=True)
            ioe.set_mode(self.pin_blue, io.PWM, invert=True)
            ioe.clear_interrupt()

            self.ioe = ioe
            self.count = self.ioe.read_rotary_encoder(1)

            self.enableInterrupt()
            self.setInterruptCallback(callback_func)
            self.setColor(12, 159, 217)  # Biohub blue
        except Exception as e:
            raise EncoderI2CError(e)

    def close(self):
        self.setColor(0, 0, 0)
        sleep(0.5)

    def disableInterrupt(self):
        self.ioe.disable_interrupt_out()

    def enableInterrupt(self):
        # Swap the interrupt pin for the Rotary Encoder breakout
        if self.I2C_ADDR == 0x0F:
            self.ioe.enable_interrupt_out(pin_swap=True)

    def setInterruptCallback(self, callback_func: Callable):
        self.ioe._gpio.remove_event_detect(self.ioe._interrupt_pin)

        def callback(_):
            curr_read = self.ioe.read_rotary_encoder(1)
            inc_or_dec = self.count - curr_read
            self.count = curr_read
            callback_func(inc_or_dec)
            self.ioe.clear_interrupt()

        self.ioe.on_interrupt(callback=callback)
        self.ioe.clear_interrupt()

    def getCount(self):
        return self.count

    def setColor(self, r, g, b):
        self.ioe.output(self.pin_red, r)
        self.ioe.output(self.pin_green, g)
        self.ioe.output(self.pin_blue, b)


if __name__ == "__main__":

    def test_callback(inc: int):
        if inc == -1:
            print("forward: What's cooking?")
        elif inc == 1:
            print("backward: Kitchen's empty.")

    encoder = PIM522RotaryEncoder(test_callback)
    encoder.setColor(12, 159, 217)

    print(f"Running for indefinitely, feel free to move the encoder! Ctrl+C to exit.")
    while True:
        sleep(5)
