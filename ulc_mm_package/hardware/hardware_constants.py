# ================ Misc constants ================ #
RPI_OUTPUT_V = 3.3
FAN_GPIO = 5
BOARD_STATUS_INDICATOR = 4

# ================ Motor controller constants ================ #

# Pin numbers in BCM, see https://pinout.xyz/
MOTOR_ENABLE = 6
MOTOR_SLEEP = 26
MOTOR_RESET = 21
MOTOR_STEP_PIN = 19
MOTOR_DIR_PIN = 16
MOTOR_FAULT_PIN = 20
MOTOR_LIMIT_SWITCH1 = 18
MOTOR_LIMIT_SWITCH2 = 15

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
ROT_INTERRUPT_PIN = 27
ROT_A_PIN = 12
ROT_B_PIN = 3
ROT_C_PIN = 11

# ================ LED Driver constants ================ #
LED_PWM_PIN = 13

# To activate analog dimming mode, the voltage must be between the following bounds. For analog
# dimming mode, the voltage must be higher than the upper bound listed below.
PWM_DIM_MODE_LOWER_THRESHOLD_V = 1
PWM_DIM_MODE_UPPER_THRESHOLD_V = 2.07
PWM_DIM_MODE_DUTYCYCLE = (
    (PWM_DIM_MODE_LOWER_THRESHOLD_V + PWM_DIM_MODE_UPPER_THRESHOLD_V) / 2
) / RPI_OUTPUT_V
ANALOG_DIM_MODE_DUTYCYCLE = 1

# To ensure linear dimming performance, PWM must be <1kHz (see datasheet pg. 19)
LED_FREQ = 50000

# ================ Pressure control constants ================ #
SERVO_5V_PIN = 17
SERVO_PWM_PIN = 12
VALVE_PIN = 8

VIDEO_PATH = "./sim_media/sample.avi"