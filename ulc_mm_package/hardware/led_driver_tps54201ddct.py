""" TPS54201DDCT - Synchronous Buck Mono-Colour/IR LED Driver

-- Important Links --
Datasheet:
    https://www.ti.com/lit/ds/symlink/tps54201.pdf?HQS=dis-dk-null-digikeymode-dsf-pf-null-wwe&ts=1631571231219&ref_url=https%253A%252F%252Fwww.ti.com%252Fgeneral%252Fdocs%252Fsuppproductinfo.tsp%253FdistId%253D10%2526gotoUrl%253Dhttps%253A%252F%252Fwww.ti.com%252Flit%252Fgpn%252Ftps54201
"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


class LEDError(Exception):
    """Base class for catching LED errors."""

@hardware
class LED_TPS5420TDDCT():
    """An LED driver class for the TPS5420TDDCT and sets the dimming mode to PWM on initialization."""