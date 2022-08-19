#! /usr/bin/python3

from time import sleep
from ulc_mm_package.hardware.pneumatic_module import PneumaticModule
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT

if __name__ == "__main__":
    led = LED_TPS5420TDDCT()
    led.turnOn()
    led.setDutyCycle(0)
    pneumatic_module = PneumaticModule()
    sleep(1)
    led.close()
    pneumatic_module.close()