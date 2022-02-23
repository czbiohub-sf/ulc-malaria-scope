""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

-- Important Links -- 
Adafruit Product Page:
    https://www.adafruit.com/product/3965
Adafruit MPRLS Python Library:
    https://github.com/adafruit/Adafruit_CircuitPython_MPRLS
Servo Motor Pololu HD-1810MG:
    https://www.pololu.com/product/1047
"""

from time import sleep
import pigpio
import board
import adafruit_mprls
from ulc_mm_package.hardware.hardware_constants import *

class PressureControlError(Exception):
    """Base class for catching all pressure control related errors."""
    pass

class PressureSensorNotInstantiated(PressureControlError):
    """Raised when the Adafruit MPRLS can not be instantiated."""
    def __init__(self):
        super().__init__("Could not instantiate pressure sensor.")

class PressureControl():
    """Class that deals with monitoring and adjusting the pressure. 

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """
    def __init__(self, servo_pin: int=SERVO_PWM_PIN, pi: pigpio.pi=None):
        self._pi = pi if pi != None else pigpio.pi()
        self.servo_pin = servo_pin

        # Frequency must be larger than the pulse width range expected by the servo (i.e > 2ms)
        self.frequency = 200

        # pigpio rounds to the nearest available frequency, see: https://abyz.me.uk/rpi/pigpio/python.html#set_PWM_frequency
        self.frequency = self._pi.set_PWM_frequency(servo_pin, self.frequency)
        freq_width_us = 1/self.frequency * 10**6

        # The three values below (dead_bandwidth, min_width, max_width) are taken from the datasheet
        self.dead_bandwidth_us = 5
        self.min_width_us = 1500 + 200 # adding some padding
        self.max_width_us = 2250

        # Convert to valid PWM value
        self.min_step_size = 5 * self.dead_bandwidth_us / freq_width_us * 255 # Times 5 to add some padding
        self.min_duty_cycle = self.min_width_us / freq_width_us * 255
        self.max_duty_cycle = self.max_width_us / freq_width_us * 255
        self.duty_cycle = self.min_duty_cycle

        # Move servo to default position (minimum, stringe fully extended out)
        self._pi.set_PWM_dutycycle(servo_pin, self.duty_cycle)

        # Instantiate pressure sensor
        # TODO: uncomment this after. Commented out for now so that the servo will work
        # try:
        #     i2c = board.I2C()
        #     self.mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)
        # except Exception:
        #     raise PressureSensorNotInstantiated()

    def close(self):
        self.setDutyCycle(self.min_duty_cycle)
        sleep(0.1)
        self._pi.set_mode(self.servo_pin, pigpio.INPUT)
        self._pi.stop()
        sleep(0.5)

    def getCurrentDutyCycle(self):
        return self.duty_cycle

    def getMaxDutyCycle(self):
        return self.max_duty_cycle

    def getMinDutyCycle(self):
        return self.min_duty_cycle

    def increaseDutyCycle(self):
        if self.duty_cycle < self.max_duty_cycle - self.min_step_size:
            self.duty_cycle += self.min_step_size
            self._pi.set_PWM_dutycycle(self.servo_pin, self.duty_cycle)

    def decreaseDutyCycle(self):
        if self.duty_cycle > self.min_duty_cycle + self.min_step_size:
            self.duty_cycle -= self.min_step_size
            self._pi.set_PWM_dutycycle(self.servo_pin, self.duty_cycle)

    def setDutyCycle(self, duty_cycle):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle < duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
                    sleep(0.01)
            else:
                while self.duty_cycle > duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()
                    sleep(0.01)
            # self.duty_cycle = duty_cycle
            # self._pi.set_PWM_dutycycle(self.servo_pin, duty_cycle)