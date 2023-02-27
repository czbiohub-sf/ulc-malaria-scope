#! /usr/bin/python3

"""
Old version of `dtoverlay_PWM`
which is being used here since the newer version runs into a strange issue with
systemd where the initialization of the pwmchip fails due to some file permissions
issue. Interestingly, running the application once (and noticing that the LED/syringe
don't work), closing it, and reopening it fixes the issue.

This script properly initializes the PWM chip when being run as a systemd script.
"""

from time import sleep

from ulc_mm_package.hardware.dtoverlay_pwm import (
    dtoverlay_PWM as dtoverlay_org,
    PWM_CHANNEL,
)

if __name__ == "__main__":
    pwm1 = dtoverlay_org(PWM_CHANNEL.PWM1)
    pwm1 = dtoverlay_org(PWM_CHANNEL.PWM2)

import subprocess
import enum


class dtoverlay_PWM_Exception(Exception):
    """Base class for all dtoverlay_PWM exceptions."""

    pass


class InvalidDutyCyclePerc(dtoverlay_PWM_Exception):
    """Raised when the duty cycle is not between 0 and 1.0."""

    pass


class dtoverlay_PWM:
    def __init__(self, channel: PWM_CHANNEL):
        self.channel = channel.value
        self.period_ns = 0
        self._start()

    def _start(self):
        cmd = """
            echo 0 > export;
            echo 1 > export;
            echo 1 > pwm0/enable;
            echo 1 > pwm1/enable;
        """
        subprocess.run(
            cmd, capture_output=True, shell=True, cwd=f"/sys/class/pwm/pwmchip0"
        )

    def setFreq(self, freq: int):
        """Sets the frequency of the PWM.

        Internally, converts the frequency to time (in ns) and sets the period.
        """
        self.period_ns = int((1 / freq) * 1e9)
        cmd = f"echo {self.period_ns} > pwm{self.channel}/period;"
        subprocess.run(
            cmd, capture_output=True, shell=True, cwd=f"/sys/class/pwm/pwmchip0"
        )

    def setDutyCycle(self, duty_cycle_perc: float):
        """Sets the dutycycle (in ns) given an '% on time'.

        Parameters
        ----------
        duty_cycle_perc: float
            Between 0 - 1.0.

        """
        if not 0 <= duty_cycle_perc <= 1:
            raise InvalidDutyCyclePerc(
                f"Duty cycle must be between 0 and 1.0. Got {duty_cycle_perc}"
            )

        duty_cycle_val = int(duty_cycle_perc * self.period_ns)
        cmd = f"echo {duty_cycle_val} > pwm{self.channel}/duty_cycle;"
        subprocess.run(
            cmd, capture_output=True, shell=True, cwd=f"/sys/class/pwm/pwmchip0"
        )

    def exit(self):
        cmd = """
        echo 0 > pwm0/enable;
        echo 0 > pwm1/enable;
        """
        subprocess.run(
            cmd, capture_output=True, shell=True, cwd=f"/sys/class/pwm/pwmchip0"
        )


if __name__ == "__main__":
    from time import sleep

    pwm = dtoverlay_PWM(PWM_CHANNEL.PWM1)
    pwm.setFreq(50000)
    pwm.setDutyCycle(0)

    sleep(3)

    pwm2 = dtoverlay_PWM(PWM_CHANNEL.PWM2)
    pwm2.setFreq(50000)
    pwm2.setDutyCycle(0)

    pwm.exit()
    pwm2.exit()
