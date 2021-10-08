# ---- Motor controller constants ---- #

# Pin numbers in BCM, see https://pinout.xyz/
DRV_FAULT_PIN = 25
STEP_PIN = 8
DIR_PIN = 7
LIMIT_SWITCH1 = 20
LIMIT_SWITCH2 = 21
ZERO_OFFSET_STEPS = 20

# DRR8825 stepping mode reference
RESOLUTION = {
                'Full': (0, 0, 0),
                'Half': (1, 0, 0),
                '1/4': (0, 1, 0),
                '1/8': (1, 1, 0),
                '1/16': (0, 0, 1),
                '1/32': (1, 0, 1)
            }

# ---- Encoder constants ---- #
ROT_A_PIN = 17
ROT_B_PIN = 27