import numpy as np

from time import sleep, perf_counter

from ulc_mm_package.hardware.hardware_constants import (
    SERVO_5V_PIN,
    SERVO_PWM_PIN,
    SERVO_FREQ,
    INVALID_READ_FLAG,
)
from ulc_mm_package.hardware.dtoverlay_pwm import PWM_CHANNEL
from ulc_mm_package.hardware.sim.dtoverlay_pwm import dtoverlay_PWM

from ulc_mm_package.hardware.real.pneumatic_module import (
    PneumaticModule as RealPneumaticModule,
)
from ulc_mm_package.hardware.pneumatic_module import (
    PressureSensorNotInstantiated,
    SyringeInMotion,
    SyringeDirection,
    SyringeEndOfTravel,
)


class PneumaticModule(RealPneumaticModule):
    """Class that deals with monitoring and adjusting the pressure.

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """

    def __init__(self, servo_pin: int = SERVO_PWM_PIN, pi=None):
        self.min_step_size = (
            0.23 - 0.16
        ) / 60  # empircally found the top/bottom vals, ~60 steps between min/max pressure
        self.min_duty_cycle = 0.16
        self.max_duty_cycle = 0.23
        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle
        self.polling_time_s = 3
        self.prev_poll_time_s = 0
        self.prev_pressure = 0
        self.io_error_counter = 0
        self.mpr_enabled = True

        self.pwm = dtoverlay_PWM(PWM_CHANNEL.PWM1)
        self.pwm.setFreq(SERVO_FREQ)
        self.pwm.setDutyCycle(self.duty_cycle)

    def close(self):
        """Move the servo to its lowest-pressure position and close."""
        self.setDutyCycle(self.max_duty_cycle)
        sleep(0.5)
        self.pwm.setDutyCycle(0)
        sleep(0.5)

    def getPressure(self):
        if perf_counter() - self.prev_poll_time_s > self.polling_time_s:
            max_attempts = 6
            while max_attempts > 0:
                # TODO: Can write in here mock errors - e.g. throw IOError
                # with x probability
                try:
                    # mock mps pressure sensor w/ uniform, from 450 hPa (max pull)
                    # to 1000 hPa (atmospheric pressure)
                    new_pressure = np.random.uniform(450, 1000)
                    self.prev_pressure = new_pressure
                    self.prev_poll_time_s = perf_counter()
                    return new_pressure
                except IOError:
                    max_attempts -= 1
                except RuntimeError:
                    max_attempts -= 1
            self.io_error_counter += 1
            return INVALID_READ_FLAG
        else:
            return self.prev_pressure
