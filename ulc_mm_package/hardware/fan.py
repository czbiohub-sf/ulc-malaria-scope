from abc import ABC

from ulc_mm_package.hardware.hardware_wrapper import hardware


class FanBase(ABC):
    def turn_on(self, pin):
        ...

    def turn_off(self, pin):
        ...

    def setup_pin(self, fan_pin):
        ...

    def turn_on_all(self):
        ...

    def turn_off_all(self):
        ...


@hardware
class Fan(FanBase):
    ...
