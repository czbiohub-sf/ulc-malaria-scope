from ulc_mm_package.hardware.hardware_constants import (
    MOTOR_ENABLE,
    MOTOR_SLEEP,
    MOTOR_RESET,
    MOTOR_STEP_PIN,
    MOTOR_DIR_PIN,
    MOTOR_FAULT_PIN,
    MOTOR_LIMIT_SWITCH1,
    MOTOR_LIMIT_SWITCH2,
    ZERO_OFFSET_STEPS,
)
from ulc_mm_package.hardware.hardware_errors import (
    MotorControllerError,
    MotorMoveTimeout,
    HomingError,
    StopMotorInterrupt,
    MotorInMotion,
    InvalidMove,
)
from ulc_mm_package.hardware.motorcontroller import Direction

class DRV8825Nema():
    def __init__(
                    self,
                    direction_pin=MOTOR_DIR_PIN,
                    step_pin=MOTOR_STEP_PIN,
                    enable_pin=MOTOR_ENABLE,
                    sleep_pin=MOTOR_SLEEP,
                    reset_pin=MOTOR_RESET,
                    fault_pin=MOTOR_FAULT_PIN,
                    motor_type="DRV8825",
                    steptype="Full",
                    lim1=MOTOR_LIMIT_SWITCH1,
                    lim2: int=None,
                    max_pos: int=None,
                ):

        self.motor_type = motor_type
        self.direction_pin = direction_pin
        self.step_pin = step_pin
        self.enable_pin = enable_pin
        self.sleep_pin = sleep_pin
        self.reset_pin = reset_pin
        self.fault_pin = fault_pin
        self.lim1 = lim1
        self.lim2 = lim2
        self.steptype = steptype
        self.pos = -1e6
        self.homed = False
        self.stop_motor = False

        # Get step degree based on steptype
        degree_value = {'Full': 1.8,
                        'Half': 0.9,
                        '1/4': .45,
                        '1/8': .225,
                        '1/16': 0.1125,
                        '1/32': 0.05625,
                        '1/64': 0.028125,
                        '1/128': 0.0140625}
        self.step_degree = degree_value[steptype]
        self.microstepping = 1.8/self.step_degree # 1, 2, 4, 8, 16, 32
        self.dist_per_step_um = self.step_degree / degree_value['Full'] * FULL_STEP_TO_TRAVEL_DIST_UM
        self.button_step = 1
        self.max_pos = int(max_pos if max_pos != None else 450*self.microstepping)

    def homeToLimitSwitches(self):
        print("Homing motor, please wait...")
        self.pos = 0
        print("Done homing.")
        self.homed = True

    def move_abs(self, pos: int=200, stepdelay=.005, verbose=False, initdelay=.05):
        self.pos = int(pos)

    def move_rel(self, steps: int=200,
                dir=Direction.CCW, stepdelay=.005, verbose=False, initdelay=.05):
        if dir.value:
            self.pos = int(self.pos + self.button_step*steps)
        else:
            self.pos = int(self.pos - self.button_step*steps)

    def threaded_move_abs(self, *args, **kwargs):
        self.pos = int(args[0])

    def threaded_move_rel(self, *args, **kwargs):
        if kwargs['dir'].value:
            self.pos = int(self.pos + self.button_step*kwargs['steps'])
        else:
            self.pos = int(self.pos - self.button_step*kwargs['steps'])
