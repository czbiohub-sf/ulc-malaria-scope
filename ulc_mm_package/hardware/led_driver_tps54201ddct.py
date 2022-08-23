""" TPS54201DDCT - Synchronous Buck Mono-Colour/IR LED Driver

See LED module under hardware/real/ for more info.

"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


class LEDError(Exception):
    """Base class for catching LED errors."""

@hardware
class LED_TPS5420TDDCT():
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""