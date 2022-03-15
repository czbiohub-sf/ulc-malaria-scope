""" TPS54201DDCT - Synchronous Buck Mono-Colour/IR LED Driver

-- Important Links -- 
Datasheet:
    https://www.ti.com/lit/ds/symlink/tps54201.pdf?HQS=dis-dk-null-digikeymode-dsf-pf-null-wwe&ts=1631571231219&ref_url=https%253A%252F%252Fwww.ti.com%252Fgeneral%252Fdocs%252Fsuppproductinfo.tsp%253FdistId%253D10%2526gotoUrl%253Dhttps%253A%252F%252Fwww.ti.com%252Flit%252Fgpn%252Ftps54201
"""

from ulc_mm_package.hardware.hardware_constants import (
    LED_PWM_PIN,
    ANALOG_DIM_MODE_DUTYCYCLE,
    PWM_DIM_MODE_DUTYCYCLE,
    PWM_DIMMING_MAX_FREQ_HZ
)
import pigpio
from time import sleep

# Set default resolution to 1000 (i.e three decimal points, e.g 0.499 -> 499, but 0.4991 -> 499.1 and would be rounded)
DUTY_CYCLE_RESOLUTION = 1000 # valid range is 25-40000 (see http://abyz.me.uk/rpi/pigpio/python.html#set_PWM_range)

class LEDError(Exception):
    """Base class for catching LED errors."""
    pass

class LED_TPS5420TDDCT():
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""
    def __init__(self, pi: pigpio.pi=None, pwm_pin: int=LED_PWM_PIN):
        self.pwm_pin = pwm_pin
        self.pwm_freq = int(PWM_DIMMING_MAX_FREQ_HZ)
        self.pwm_duty_cycle = self._convertDutyCyclePercentToPWMVal(ANALOG_DIM_MODE_DUTYCYCLE)
        self._pi = pi if pi != None else pigpio.pi()
        self._pi = pigpio.pi()

        # Set the dimming mode (see datasheet, page 17)
        self._pi.hardware_PWM(self.pwm_pin, 5000, self.pwm_duty_cycle)
        sleep(0.0005)
        self._pi.hardware_PWM(self.pwm_pin, self.pwm_freq, 0)

    def close(self):
        self._pi.set_PWM_dutycycle(self.pwm_pin, 0)
        self._pi.stop()
        sleep(0.5)

    def _convertDutyCyclePercentToPWMVal(self, duty_cycle_percentage: float):
        return int(1e6*duty_cycle_percentage)

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
            pwm_val = self._convertDutyCyclePercentToPWMVal(duty_cycle_perc)
            self._pi.hardware_PWM(self.pwm_pin, self.pwm_freq, pwm_val)
        except Exception:
            raise LEDError()