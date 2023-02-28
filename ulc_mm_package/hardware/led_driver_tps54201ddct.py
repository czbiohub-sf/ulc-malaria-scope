""" TPS54201DDCT - Synchronous Buck Mono-Colour/IR LED Driver

See LED module under hardware/real/ for more info.

"""

from abc import ABC

from ulc_mm_package.hardware.hardware_wrapper import hardware


class LEDError(Exception):
    """Base class for catching LED errors."""


class LED_TPS5420TDDCT_Base(ABC):
    @property
    def pwm_duty_cycle(self):
        ...

    def turnOn(self):
        ...

    def turnOff(self):
        ...

    def close(self):
        ...

    def setDutyCycle(self, duty_cycle_perc: float):
        ...


@hardware
class LED_TPS5420TDDCT(LED_TPS5420TDDCT_Base):
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""
