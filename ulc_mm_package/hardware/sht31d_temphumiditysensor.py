""" SHT3x-DIS - Humidity and Temperature Sensor

See HT sensor module under hardware/real/ for more info.

"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


class TemperatureSensorNotInstantiated(Exception):
    """Raised when the Adafruit SHT3x can not be instantiated."""

    def __init__(self):
        super().__init__("Could not instantiate temperature/humidity sensor.")


@hardware
class SHT3X:
    """A wrapper around Adafruit's SHT3X temp/humidity sensor driver.

    This class only exists to allow for extensibility if the need arises.
    """
