# ================ Misc constants ================ #
RPI_OUTPUT_V = 3.3

# ================ Motor controller constants ================ #

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

# ================ Encoder constants ================ #
ROT_A_PIN = 17
ROT_B_PIN = 27
ROT_SWITCH = 22

# ================ LED Driver constants ================ #
LED_PWM_PIN = 13

# To activate PWM dimming mode, the voltage must be between the following bounds. For the analog 
# dimming mode, the voltage must be higher than the upper bound listed below.
PWM_DIM_MODE_LOWER_THRESHOLD_V = 1
PWM_DIM_MODE_UPPER_THRESHOLD_V = 2.07
PWM_DIM_MODE_DUTYCYCLE = ((PWM_DIM_MODE_LOWER_THRESHOLD_V + PWM_DIM_MODE_UPPER_THRESHOLD_V) / 2) / RPI_OUTPUT_V

# To ensure linear dimming performance, PWM must be <1kHz (see datasheet pg. 19)
PWM_DIMMING_MAX_FREQ_HZ = 1000