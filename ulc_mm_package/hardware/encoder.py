""" Adafruit Rotary Encoder (PEC11-4215F-S24 encoder w/ 6mm knob)

-- Important Links -- 
Adafruit Product Page:
    https://www.adafruit.com/product/377
Encoder Datasheet:
    https://cdn-shop.adafruit.com/datasheets/pec11.pdf
Knob Datasheet (mechanical dimensions):
    https://cdn-shop.adafruit.com/datasheets/EPD-200732.pdf
"""

from typing import Callable
import pigpio

'''The lookup table maps the state transition of the two encoder pins:
OLD |NEW|BINARY |--DIR--
AB  |AB |-------|-------
00  |00 |0000   |  0
00  |01 |0001   | -1
00  |10 |0010   | +1
00  |11 |0011   |  0
01  |00 |0100   | +1
01  |01 |0101   |  0
01  |10 |0110   |  0
01  |11 |0111   | -1
...
etc.

There are 2^4=16 possible states which can be represented as a 4-bit binary number (XXYY).
XX represent the previous position (pin A, pin B). YY represent the current read out.
This 4-bit number can be used to index into the lookup table and determine how to 
increment the encoder count.
'''

# ==================== Main class ===============================
class Encoder():
    def __init__(self, pin_a: int, pin_b: int, pi: pigpio.pi=None, custom_callback: Callable = None):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.lookup_table = [0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0]
        self.encoder_value = 0b0000
        self.encoder_count = 0
        self._pi = pi if pi != None else pigpio.pi()
        self.custom_callback = custom_callback
        self.last_dir = 0

        # Set up GPIO and callbacks
        self._pi.set_mode(self.pin_a, pigpio.INPUT)
        self._pi.set_pull_up_down(self.pin_a, pigpio.PUD_DOWN)
        self._pi.set_mode(self.pin_b, pigpio.INPUT)
        self._pi.set_pull_up_down(self.pin_b, pigpio.PUD_DOWN)
        self.enableEncoder()
        self.enabled = True

    def enableEncoder(self):
        self.cb1 = self._pi.callback(self.pin_a, pigpio.EITHER_EDGE, self.encoderISR)
        self.cb2 = self._pi.callback(self.pin_b, pigpio.EITHER_EDGE, self.encoderISR)

    def disableEncoder(self):
        self.cb1.cancel()
        self.cb2.cancel()

    def isEnabled(self):
        return self.enabled

    def encoderISR(self, *args):
        # Read the two input pins and convert it to a 2-bit binary (i.e 00 / 10 / 01 / 11)
        a = self._pi.read(self.pin_a)
        b = self._pi.read(self.pin_b)
        val = a << 1 | b

        # Left shift the encoder value and OR with the current readout  
        # (OLD, NEW) --> (NEW, NEW') (the previous new becomes old and we add
        # in the current readout into the 2 least significant bits)
        # Lastly bitwise AND with 15 (1111) to retain only last 4 bits
        self.encoder_value = ((self.encoder_value << 2) | val) & 0b1111
        
        # Finally use the lookup table to figure out how the encoder has moved
        # and increment
        increment = self.lookup_table[self.encoder_value]
        self.encoder_count += increment

        # Call the custom callback with the movement direction (1, 0, -1)
        if self.encoder_count % 4 == 0 and self.custom_callback:
            self.custom_callback(increment)

    def getRawCount(self):
        return self.encoder_count
    
    def getDetentCount(self):
        return self.encoder_count // 4

    def resetCount(self):
        self.encoder_count = 0