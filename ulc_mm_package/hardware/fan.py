import pigpio
from ulc_mm_package.hardware.hardware_constants import FAN_GPIO

class Fan():
    def __init__(self, fan_pin: int=FAN_GPIO):
        self._pi = pigpio.pi()
        self.fan_pin = FAN_GPIO
        self._pi.set_mode(self.fan_pin, pigpio.OUTPUT)
        self._pi.set_pull_up_down(self.fan_pin, pigpio.PUD_DOWN)

    def turn_on(self):
        self._pi.write(self.fan_pin, 1)

    def turn_off(self):
        self._pi.write(self.fan_pin, 0)