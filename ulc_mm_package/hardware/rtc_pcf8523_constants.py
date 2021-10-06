""" Register/opcode constants for the PCF8523

-- Important Links -- 
Datasheet:
    https://www.nxp.com/docs/en/data-sheet/PCF8523.pdf
"""

### Control Registers ###
CONTROL_1 = 0x00
CONTROL_2 = 0x01
CONTROL_3 = 0x02

### Control register opcodes and bit address ###

# Control register 1 opcodes
CAP_SEL =   7
T =         6
STOP =      5
SR =        4
TWELVE_TWENTYFOUR = 3 # Written as "12_24" in the datasheet
SIE =       2
AIE =       1
CIE =       0

# Control register 2 opcodes
WTAF =      7
CTAF =      6
CTBF =      5
SF =        4
AF =        3
WTAIE =     2
CAIE =      1
CTBIE =     0

# Control register 3 opcodes
PM =    [None]*2
BSF =   3
BLF =   2
BSIE =  1
BLIE =  0

# Time and date registers
SECONDS =   0x03
MINUTES =   0x04
HOURS =     0x05
DAYS =      0x06
WEEKDAYS =  0x07
MONTHS =    0x08
YEARS =     0x09

# Alarm registers
MINUTE_ALARM =  0x0A
HOUR_ALARM =    0x0B
DAY_ALARM =     0x0C
WEEKDAY_ALARM = 0x0D

# Offset register
OFFSET = 0x0E
