from time import sleep

from ulc_mm_package.hardware.hardware_constants import (
    LED_PWM_PIN,
    ANALOG_DIM_MODE_DUTYCYCLE,
    LED_FREQ
)
from ulc_mm_package.hardware.led_driver_tps54201ddct import LEDError
from ulc_mm_package.hardware.dtoverlay_pwm import dtoverlay_PWM, PWM_CHANNEL


class LED_TPS5420TDDCT():
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""

    def __init__(self):
        self._isOn = False
        self.pwm_freq = int(LED_FREQ)
        self.pwm_duty_cycle = ANALOG_DIM_MODE_DUTYCYCLE
        self.pwm = dtoverlay_PWM(PWM_CHANNEL.PWM2)

        # Set the dimming mode (see datasheet, page 17)
        self.pwm.setFreq(50000)
        self.pwm.setDutyCycle(ANALOG_DIM_MODE_DUTYCYCLE)
        sleep(0.0005)
        self.pwm.setFreq(self.pwm_freq)
        self.pwm.setDutyCycle(0)

    def close(self):
        self.pwm.exit()
        sleep(0.5)

    def setDutyCycle(self, duty_cycle_perc: float):
        """Set the duty cycle to a desired percentage.

        Parameters
        ----------
        duty_cycle_perc: float
            To run at 50%, the argument passed must be 0.5. Note that the default duty cycle
            resolution is at 1000, i.e values such as 0.501 would be set correctly (501),
            however 0.5018 would be subject to rounding (502).
        """

        try:
            if self._isOn:
                self.pwm_duty_cycle = duty_cycle_perc
                self.pwm.setDutyCycle(self.pwm_duty_cycle)
        except Exception as e:
            raise LEDError(e)

    def turnOn(self):
        self._isOn = True

    def turnOff(self):
        self.setDutyCycle(0)
        self._isOn = False
