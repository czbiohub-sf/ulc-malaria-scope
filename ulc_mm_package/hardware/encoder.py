# ========================= HEADER ===================================
# title             :encoder.py
# description       :An Encoder class using a binary lookup table to quickly determine encoder clicks + direction
# Main author       :Ilakkiyan Jeyakumar

# ========================== IMPORTS ======================
import RPi.GPIO as GPIO
from hardware_constants import *

'''The lookup table maps the state transition of the two encoder pins:
OLD |NEW|BINARY |--DIR--
AB  |AB |-------|-------
00  |00 |0000   | 0 (can't tell)
00  |01 |0001   | -1
00  |10 |0010   | +1
00  |11 |0011   | 0 (can't tell)
01  |00 |0100   | +1
01  |01 |0101   | 0
01  |10 |0110   | 0
01  |11 |0111   | -1
...
etc.

There are 2^4=16 possible states which can be represented as a 4-bit binary number (XXYY).
XX represent the previous position (pin A, pin B). YY represent the current read out.
This 4-bit number can be used to index into the lookup table and determine how to 
increment the encoder count.
'''

class Encoder():
    def __init__(self, pin_a=ROT_A_PIN, pin_b=ROT_B_PIN):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.lookup_table = [0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0]
        self.encoder_value = 0b0000
        self.encoder_count = 0

        # Set up GPIO and callbacks
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin_a, GPIO.IN)
        GPIO.setup(pin_b, GPIO.IN)
        GPIO.add_event_detect(self.pin_a, GPIO.RISING, callback=self.encoderISR)
        GPIO.add_event_detect(self.pin_b, GPIO.RISING, callback=self.encoderISR)

    def encoderISR(self):
        # Read the two input pins and convert it to a 2-bit binary (i.e 00 / 10 / 01 / 11)
        val = GPIO.input(self.pin_a) << 1 | GPIO.input(self.pin_b)

        # Left shift the encoder value and OR with the current readout
        # (OLD, NEW) --> (NEW, NEW') (the previous new becomes old and we add
        # in the current readout into the 2 least significant bits)
        self.encoder_value = (self.encoder_value << 2) | val

        # Finally use the lookup table to figure out how the encoder has moved
        # and increment
        self.encoder_count += self.lookup_table[self.encoder_value]