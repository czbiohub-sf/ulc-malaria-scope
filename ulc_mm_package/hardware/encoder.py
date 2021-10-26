# ========================= HEADER ===================================
# title             :encoder.py
# description       :An Encoder class using a binary lookup table to quickly determine encoder clicks + direction
# Main author       :Ilakkiyan Jeyakumar

# ========================== IMPORTS ======================
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
    def __init__(self, pin_a: int, pin_b: int, pi: pigpio.pi=None):
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.lookup_table = [0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0]
        self.encoder_value = 0b0000
        self.encoder_count = 0
        self._pi = pi if pi != None else pigpio.pi()

        # Set up GPIO and callbacks
        self._pi.set_mode(self.pin_a, pigpio.INPUT)
        self._pi.set_mode(self.pin_b, pigpio.INPUT)
        self._pi.callback(self.pin_a, pigpio.RISING_EDGE, self.encoderISR)
        self._pi.callback(self.pin_b, pigpio.RISING_EDGE, self.encoderISR)

    def encoderISR(self, *args):
        # Read the two input pins and convert it to a 2-bit binary (i.e 00 / 10 / 01 / 11)
        val = self._pi.read(self.pin_a) << 1 | self._pi.read(self.pin_b)

        # Left shift the encoder value and OR with the current readout  
        # (OLD, NEW) --> (NEW, NEW') (the previous new becomes old and we add
        # in the current readout into the 2 least significant bits)
        # Lastly bitwise AND with 15 (1111) to retain only last 4 bits
        self.encoder_value = ((self.encoder_value << 2) | val) & 15

        # Finally use the lookup table to figure out how the encoder has moved
        # and increment
        self.encoder_count += self.lookup_table[self.encoder_value]

    def getCount(self):
        return self.encoder_count

    def resetCount(self):
        self.encoder_count = 0