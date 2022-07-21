""" Dummy functions simulating hardware objects for UI testing
"""

import enum
import cv2
import numpy as np
import scipy

from ulc_mm_package.hardware.hardware_constants import *

from typing import Callable
from time import sleep

# Camera constants
_DEFAULT_EXPOSURE_MS = 0.5

# Pressure control constants
INVALID_READ_FLAG = -1
DEFAULT_AFC_DELAY_S = 10
FASTER_FEEDBACK_DELAY_S = 3

# Simulation specific constants
VIDEO_PATH = "./media/2022-01-21.avi"


################## camera.py ##################

class CameraError(Exception):
    pass


class BaslerCamera():
    def __init__(self):
        try:
            self.binning = 1
            self.exposureTime_ms = _DEFAULT_EXPOSURE_MS
            # self.camera.PixelFormat.SetValue("Mono8")
            # self.grabStrategy = GrabStrategy.LATEST_IMAGE_ONLY

            # Simulation specific
            self.video = cv2.VideoCapture(VIDEO_PATH)
            self.frame_count = int(self.video.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video.get(cv2.CAP_PROP_FPS)

            success, frame = self.video.read() 
            self.frames = np.zeros((self.frame_count - 1, frame.shape[0], frame.shape[1]))

            success = True
            # first frame previously opened already
            index = 0

            while success and index < self.frame_count - 1:
                success, frame = self.video.read()
                self.frames[index] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
                index += 1

        except Exception as e:
            print(e)
            raise CameraError("Camera could not be instantiated.")

    # Superclass methods
    def setBinning(self, bin_factor=1, mode="Average"):
        self.binning = bin_factor

    def getBinning(self):
        return self.binning

    # Custom methods
    def yieldImages(self):
        index = 0

        while True:
            yield self.frames[index]
            index += 1
            if index == self.frame_count - 1:
                index = 0
            sleep(1 / self.fps)

    def stopAcquisition(self):
        pass

    def deactivateCamera(self):
        pass


# class AVTCamera:


class CameraIterator:
    def __init__(self, camera):
        self._camera = camera
        self._index = 0

    def __next__(self):
        if self._index < len(self._team._images):
            return self._camera._images[self._images]
        raise StopIteration


################## motorcontroller.py ##################

class MotorControllerError(Exception):
    pass


class MotorInMotion(MotorControllerError):
    pass


class Direction(enum.Enum):
    CW = True
    CCW = False


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

        # simulation specific variable
        self.button_step = 10

        self.max_pos = int(max_pos if max_pos != None else 450*self.microstepping)

    def homeToLimitSwitches(self):
        print("Homing motor, please wait...")
        self.pos = 0
        print("Done homing.")
        self.homed = True

    def move_abs(self, pos: int=200, stepdelay=.005, verbose=False, initdelay=.05):
        self.pos = int(pos)

    # TODO figure out why different keyword arguments?
    def move_rel(self, steps: int=200, 
                dir=Direction.CCW, stepdelay=.005, verbose=False, initdelay=.05):
        if dir.value:
            self.pos = int(self.pos + self.button_step*steps)
        else:
            self.pos = int(self.pos - self.button_step*steps)

    def threaded_move_rel(self, *args, **kwargs):
        if kwargs['dir'].value:
            self.pos = int(self.pos + self.button_step*kwargs['steps'])
        else:
            self.pos = int(self.pos - self.button_step*kwargs['steps'])

    def threaded_move_abs(self, *args, **kwargs):
        self.pos = int(args[0])


################## led_driver_tps54201ddct.py ##################

class LEDError(Exception):
    pass


class LED_TPS5420TDDCT():
    def __init__(self, pwm_pin: int=LED_PWM_PIN):
        self._isOn = False
        self.pwm_pin = pwm_pin
        self.pwm_freq = int(LED_FREQ)
        self.pwm_duty_cycle = 10

    def close(self):
        self.pwm_duty_cycle = 0
        # sleep(0.5)

    def _convertPWMValToDutyCyclePerc(self, pwm_val: int) -> float:
        return pwm_val / 1e6

    def setDutyCycle(self, duty_cycle_perc: float):
        self.pwm_duty_cycle = self._convertDutyCyclePercentToPWMVal(duty_cycle_perc)

    def _convertDutyCyclePercentToPWMVal(self, duty_cycle_percentage: float) -> int:
        return int(1e6*duty_cycle_percentage)

    def turnOn(self):
        self._isOn = True

    def turnOff(self):
        self.setDutyCycle(0)
        self._isOn = False


################## pim522_rotary_encoder.py ##################

class PIM522RotaryEncoder:
    def __init__(self, callback_func: Callable):
        self.I2C_ADDR = 0x0F  # 0x18 for IO Expander, 0x0F for the encoder breakout
        self.pin_red = 1
        self.pin_green = 7
        self.pin_blue = 2

    def setColor(self, r, g, b):
        pass

    def close(self):
        # self.setColor(0, 0, 0)
        # sleep(0.5)
        pass


################## pressure_control.py ##################

class PressureControlError(Exception):
    pass


class PressureLeak(PressureControlError):
    def __init__(self):
        super().__init__("Pressure leak detected.")


class PressureControl():
    def __init__(self, servo_pin: int=SERVO_PWM_PIN):
        # self._pi = pi if pi != None else pigpio.pi()
        self.servo_pin = servo_pin

        self.min_step_size = 10
        self.min_duty_cycle = 1600
        self.max_duty_cycle = 2200
        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle
        self.polling_time_s = 3
        self.prev_poll_time_s = 0
        self.prev_pressure = 0
        self.io_error_counter = 0
        self.prev_time_s = 0
        self.control_delay_s = 0.2

        # Active flow control variables
        self.flowrate_target = 0
        self.flow_rate_y = 0
        self.prev_afc_time_s = 0
        self.afc_delay_s = DEFAULT_AFC_DELAY_S

        # Added variables 
        self.curr_pressure = self.prev_pressure

    def getPressure(self, apc_on: bool=False):
        return self.curr_pressure

    def getCurrentDutyCycle(self):
        return self.duty_cycle

    def getMaxDutyCycle(self):
        return self.max_duty_cycle

    def getMinDutyCycle(self):
        return self.min_duty_cycle

    def increaseDutyCycle(self):
        if self.duty_cycle <= self.max_duty_cycle - self.min_step_size:
            self.duty_cycle += self.min_step_size
            # sleep(0.01)

    def decreaseDutyCycle(self):
        if self.duty_cycle >= self.min_duty_cycle + self.min_step_size:
            self.duty_cycle -= self.min_step_size
            # sleep(0.01)

    def setDutyCycle(self, duty_cycle: int):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle <= duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
            else:
                while self.duty_cycle >= duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()

    def close(self):
        self.setDutyCycle(self.max_duty_cycle)
        # sleep(0.5)
        # sleep(0.5)

    # no implemented function in hardware object?
    def holdPressure(target_pressure):
        pass


################## fan.py ##################

class Fan():
    def __init__(self, fan_pin: int=FAN_GPIO):
        pass

    def turn_on(self):
        pass

    def turn_off(self):
        pass