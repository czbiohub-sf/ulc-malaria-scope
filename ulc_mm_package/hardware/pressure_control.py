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

        # Convert to valid PWM value
        self.min_step_size = 50
        self.min_duty_cycle = 1600
        self.max_duty_cycle = 2200
        self.duty_cycle = self.max_duty_cycle

        # Move servo to default position (minimum, stringe fully extended out)
        self._pi.set_pull_up_down(servo_pin, pigpio.PUD_DOWN)
        self._pi.set_servo_pulsewidth(servo_pin, self.duty_cycle)

        # Instantiate pressure sensor
        # TODO: uncomment this after. Commented out for now so that the servo will work
        # try:
        #     i2c = board.I2C()
        #     self.mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)
        # except Exception:
        #     raise PressureSensorNotInstantiated()

    def close(self):
        self.setDutyCycle(self.max_duty_cycle)
        sleep(0.1)
        self.setDutyCycle(0)
        sleep(0.5)
        self._pi.stop()
        sleep(0.5)

    def getCurrentDutyCycle(self):
        return self.duty_cycle

    def getMaxDutyCycle(self):
        return self.max_duty_cycle

    def getMinDutyCycle(self):
        return self.min_duty_cycle

    def increaseDutyCycle(self):
        if self.duty_cycle <= self.max_duty_cycle - self.min_step_size:
            self.duty_cycle += self.min_step_size
            self._pi.set_servo_pulsewidth(self.servo_pin, self.duty_cycle)

    def decreaseDutyCycle(self):
        if self.duty_cycle >= self.min_duty_cycle + self.min_step_size:
            self.duty_cycle -= self.min_step_size
            self._pi.set_servo_pulsewidth(self.servo_pin, self.duty_cycle)

    def setDutyCycle(self, duty_cycle):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle <= duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
                    sleep(0.01)
            else:
                while self.duty_cycle >= duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()
                    sleep(0.01)
            # self.duty_cycle = duty_cycle
            # self._pi.set_PWM_dutycycle(self.servo_pin, duty_cycle)