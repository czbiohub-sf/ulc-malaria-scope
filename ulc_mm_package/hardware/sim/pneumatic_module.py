from time import sleep, perf_counter
from typing import Tuple

import numpy as np

from ulc_mm_package.hardware.hardware_constants import (
    SERVO_5V_PIN,
    SERVO_PWM_PIN,
    SERVO_FREQ,
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
    PressureSensorRead,
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
        self.prev_status = PressureSensorRead.ALL_GOOD
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

    def getPressure(self) -> Tuple[float, PressureSensorRead]:
        ### TODO - mimic the real pressure sensor more
        # TODO: Can write in here mock errors - e.g. throw IOError

        # mock mps pressure sensor w/ uniform, from 450 hPa (max pull)
        # to 1000 hPa (atmospheric pressure)

        # Put this in here to pass oracle's pressure check
        if self.getCurrentDutyCycle() == self.getMaxDutyCycle():
            return (1025, PressureSensorRead.ALL_GOOD)
        elif self.getCurrentDutyCycle() == self.getMinDutyCycle():
            return (450, PressureSensorRead.ALL_GOOD)

        new_pressure, status = (
            np.random.uniform(450, 1000),
            PressureSensorRead.ALL_GOOD,
        )
        return (new_pressure, status)
