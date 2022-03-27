# ================ Misc constants ================ #
RPI_OUTPUT_V = 3.3

# ================ Motor controller constants ================ #

# Pin numbers in BCM, see https://pinout.xyz/
MOTOR_SLEEP = 6
MOTOR_FAULT_PIN = 16
MOTOR_STEP_PIN = 19
MOTOR_DIR_PIN = 20
MOTOR_RESET = 21
MOTOR_LIMIT_SWITCH1 = 24
MOTOR_ENABLE = 26
ZERO_OFFSET_STEPS = 20

# DRR8825 stepping mode reference
RESOLUTION = {
    "Full": (0, 0, 0),
    "Half": (1, 0, 0),
    "1/4": (0, 1, 0),
    "1/8": (1, 1, 0),
    "1/16": (0, 0, 1),
    "1/32": (1, 0, 1),
}

# ================ Motor constants ================ #
FULL_STEP_TO_TRAVEL_DIST_UM = 0.56


# ================ Encoder constants ================ #
ROT_A_PIN = 17
ROT_B_PIN = 27
ROT_SWITCH = 22

# ================ LED Driver constants ================ #
LED_PWM_PIN = 13

# To activate analog dimming mode, the voltage must be between the following bounds. For the analog
# dimming mode, the voltage must be higher than the upper bound listed below.
PWM_DIM_MODE_LOWER_THRESHOLD_V = 1
PWM_DIM_MODE_UPPER_THRESHOLD_V = 2.07
PWM_DIM_MODE_DUTYCYCLE = (
    (PWM_DIM_MODE_LOWER_THRESHOLD_V + PWM_DIM_MODE_UPPER_THRESHOLD_V) / 2
) / RPI_OUTPUT_V
ANALOG_DIM_MODE_DUTYCYCLE = 1

# To ensure linear dimming performance, PWM must be <1kHz (see datasheet pg. 19)
PWM_DIMMING_MAX_FREQ_HZ = 40000

# ================ Pressure control constants ================ #
SERVO_PWM_PIN = 12
VALVE_PIN = 16
