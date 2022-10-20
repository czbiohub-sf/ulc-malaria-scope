import enum
import subprocess


class PWM_CHANNEL(enum.Enum):
    PWM1 = 0
    PWM2 = 1


class dtoverlay_PWM_Exception(Exception):
    """Base class for all dtoverlay_PWM exceptions."""

    pass


class InvalidDutyCyclePerc(dtoverlay_PWM_Exception):
    """Raised when the duty cycle is not between 0 and 1.0."""

    pass


class dtoverlay_PWM:
    _started = False

    def __init__(self, channel: PWM_CHANNEL):
        self.channel = channel.value
        self.period_ns = 0
        if not dtoverlay_PWM._started:
            self._start()
            dtoverlay_PWM._started = True

    def _atomic_write_to_file(self, file, write_content):
        with open(file, "w") as g:
            g.write(write_content)

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
        self._atomic_write_to_file(
            f"/sys/class/pwm/pwmchip0/pwm{self.channel}/period", str(self.period_ns)
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
        self._atomic_write_to_file(
            f"/sys/class/pwm/pwmchip0/pwm{self.channel}/duty_cycle", str(duty_cycle_val)
        )

    def exit(self):
        cmd = """
        echo 0 > pwm0/enable;
        echo 0 > pwm0/enable;
        echo 0 > pwm1/enable;
        echo 0 > pwm1/enable;
        """
        subprocess.run(
            cmd, capture_output=True, shell=True, cwd=f"/sys/class/pwm/pwmchip0"
        )
        dtoverlay_PWM._started = True


if __name__ == "__main__":
    from time import sleep

    pwm = dtoverlay_PWM(PWM_CHANNEL.PWM2)
    pwm.setFreq(50000)
    pwm.setDutyCycle(0.5)

    sleep(3)

    pwm.exit()
