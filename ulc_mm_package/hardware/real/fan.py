import pigpio

from ulc_mm_package.hardware.hardware_constants import FAN_GPIO, CAM_FAN_1, CAM_FAN_2


class Fan:
    def __init__(self, fan_pin: int = FAN_GPIO):
        self._pi = pigpio.pi()

        self.setup_pin(FAN_GPIO)
        self.setup_pin(CAM_FAN_1)
        self.setup_pin(CAM_FAN_2)

    def turn_on(self, pin):
        self._pi.write(pin, 1)

    def turn_off(self, pin):
        self._pi.write(pin, 0)

    def setup_pin(self, fan_pin):
        self._pi.set_mode(fan_pin, pigpio.OUTPUT)
        self._pi.set_pull_up_down(fan_pin, pigpio.PUD_DOWN)

    def turn_on_all(self):
        self.turn_on(FAN_GPIO)
        self.turn_on(CAM_FAN_1)
        self.turn_on(CAM_FAN_2)

    def turn_off_all(self):
        self.turn_off(FAN_GPIO)
        self.turn_off(CAM_FAN_1)
        self.turn_off(CAM_FAN_2)
