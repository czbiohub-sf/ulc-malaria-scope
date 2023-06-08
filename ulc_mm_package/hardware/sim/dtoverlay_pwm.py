from ulc_mm_package.hardware.dtoverlay_pwm import PWM_CHANNEL


class dtoverlay_PWM:
    _started = False

    def __init__(self, channel: PWM_CHANNEL):
        self.channel = channel.value
        self.period_ns = 0
        if not dtoverlay_PWM._started:
            self._start()
            dtoverlay_PWM._started = True

    def _atomic_write_to_file(self, file, write_content):
        ...

    def _start(self):
        ...

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
        ...
