""" TPS54201DDCT - Synchronous Buck Mono-Colour/IR LED Driver

-- Important Links -- 
Datasheet:
    https://www.ti.com/lit/ds/symlink/tps54201.pdf?HQS=dis-dk-null-digikeymode-dsf-pf-null-wwe&ts=1631571231219&ref_url=https%253A%252F%252Fwww.ti.com%252Fgeneral%252Fdocs%252Fsuppproductinfo.tsp%253FdistId%253D10%2526gotoUrl%253Dhttps%253A%252F%252Fwww.ti.com%252Flit%252Fgpn%252Ftps54201
"""

from ulc_mm_package.hardware.hardware_constants import (
    LED_PWM_PIN,
    ANALOG_DIM_MODE_DUTYCYCLE,
    LED_FREQ
)
from ulc_mm_package.hardware.dtoverlay_pwm import dtoverlay_PWM, PWM_CHANNEL
import pigpio
from time import sleep

class LEDError(Exception):
    """Base class for catching LED errors."""
    pass

class LED_TPS5420TDDCT():
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""

    def __init__(self):
        self._isOn = False
        self.pwm_freq = int(LED_FREQ)
        self.pwm_duty_cycle = ANALOG_DIM_MODE_DUTYCYCLE
        self.pwm = dtoverlay_PWM()

        # Set the dimming mode (see datasheet, page 17)
        self.pwm.setFreq(PWM_CHANNEL.PWM1, 5000)
        self.pwm.setDutyCycle(PWM_CHANNEL.PWM1, ANALOG_DIM_MODE_DUTYCYCLE)
        sleep(0.0005)
        self.pwm.setFreq(PWM_CHANNEL.PWM1, self.pwm_freq)
        self.pwm.setDutyCycle(PWM_CHANNEL.PWM1, 0)

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
                self.pwm.setDutyCycle(PWM_CHANNEL.PWM1, self.pwm_duty_cycle)
        except Exception as e:
            raise LEDError(e)

    def turnOn(self):
        self._isOn = True

    def turnOff(self):
        self.setDutyCycle(0)
        self._isOn = False