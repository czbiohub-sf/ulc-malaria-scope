""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

-- Important Links --
Adafruit Product Page:
    https://www.adafruit.com/product/3965
Adafruit MPRLS Python Library:
    https://github.com/adafruit/Adafruit_CircuitPython_MPRLS
Servo Motor Pololu HD-1810MG:
    https://www.pololu.com/product/1047
"""

import functools
import threading
import pigpio
import board
import adafruit_mprls

from time import sleep, perf_counter

from ulc_mm_package.hardware.hardware_constants import (
    SERVO_5V_PIN,
    SERVO_PWM_PIN,
    SERVO_FREQ,
    INVALID_READ_FLAG,
)
from ulc_mm_package.hardware.dtoverlay_pwm import (
    dtoverlay_PWM,
    PWM_CHANNEL,
)
from ulc_mm_package.hardware.pneumatic_module import (
    PressureSensorNotInstantiated,
    SyringeInMotion,
    SyringeDirection,
    SyringeEndOfTravel,
)


SYRINGE_LOCK = threading.Lock()


def lockNoBlock(lock):
    def lockDecorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not lock.locked():
                with lock:
                    return func(*args, **kwargs)
            else:
                raise SyringeInMotion

        return wrapper

    return lockDecorator


class PneumaticModule:
    """Class that deals with monitoring and adjusting the pressure.

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """

    def __init__(self, servo_pin: int = SERVO_PWM_PIN, pi: pigpio.pi = None):
        self._pi = pi if pi != None else pigpio.pi()
        self.servo_pin = servo_pin

        self.min_step_size = (
            0.23 - 0.16
        ) / 60  # empircally found the top/bottom vals, ~60 steps between min/max pressure
        self.min_duty_cycle = 0.16
        self.max_duty_cycle = 0.23
        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle
        self.polling_time_s = 3
        self.prev_poll_time_s = 0
        self.prev_pressure = 0
        self.io_error_counter = 0
        self.mpr_enabled = False
        self.mpr_err_msg = ""

        # Toggle 5V line
        self._pi.write(SERVO_5V_PIN, 1)

        # Move servo to default position (minimum, stringe fully extended out)
        self._pi.set_pull_up_down(servo_pin, pigpio.PUD_DOWN)

        self.pwm = dtoverlay_PWM(PWM_CHANNEL.PWM1)
        self.pwm.setFreq(SERVO_FREQ)
        self.pwm.setDutyCycle(self.duty_cycle)

        # Instantiate pressure sensor
        try:
            i2c = board.I2C()
            self.mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)
            self.mpr_enabled = True
        except Exception as e:
            self.mpr_err_msg = f"{e}"
            self.mpr_enabled = False

    def close(self):
        """Move the servo to its lowest-pressure position and close."""
        self.setDutyCycle(self.max_duty_cycle)
        sleep(0.5)
        self._pi.stop()
        self.pwm.setDutyCycle(0)
        sleep(0.5)

    def getCurrentDutyCycle(self):
        return self.duty_cycle

    def getMaxDutyCycle(self):
        return self.max_duty_cycle

    def getMinDutyCycle(self):
        return self.min_duty_cycle

    def increaseDutyCycle(self):
        if self.isMovePossible(SyringeDirection.UP):
            self.duty_cycle += self.min_step_size
            self.pwm.setDutyCycle(self.duty_cycle)
            sleep(0.01)
        else:
            raise SyringeEndOfTravel()

    def decreaseDutyCycle(self):
        if self.isMovePossible(SyringeDirection.DOWN):
            self.duty_cycle -= self.min_step_size
            self.pwm.setDutyCycle(self.duty_cycle)
            sleep(0.01)
        else:
            raise SyringeEndOfTravel()

    @lockNoBlock(SYRINGE_LOCK)
    def setDutyCycle(self, duty_cycle: int):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle <= duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
            else:
                while self.duty_cycle >= duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()

    def threadedDecreaseDutyCycle(self, *args, **kwargs):
        if not SYRINGE_LOCK.locked():
            threading.Thread(target=self.decreaseDutyCycle, *args, **kwargs).start()
        else:
            raise SyringeInMotion

    def threadedIncreaseDutyCycle(self, *args, **kwargs):
        if not SYRINGE_LOCK.locked():
            threading.Thread(target=self.increaseDutyCycle, *args, **kwargs).start()
        else:
            raise SyringeInMotion

    def threadedSetDutyCycle(self, *args, **kwargs):
        if not SYRINGE_LOCK.locked():
            threading.Thread(target=self.setDutyCycle, args=args, kwargs=kwargs).start()
        else:
            raise SyringeInMotion

    def sweepAndGetPressures(self):
        """Sweep the syringe and read pressure values."""
        min, max = self.getMinDutyCycle(), self.getMaxDutyCycle()
        self.setDutyCycle(max)
        pressure_readings_hpa = []
        while self.duty_cycle > min:
            pressure_readings_hpa.append(self.getPressure())
            sleep(0.5)
            self.decreaseDutyCycle()
        return pressure_readings_hpa

    def getPressure(self):
        """Read and return the latest pressure value if it has been at least `polling_time_s` seconds,
        otherwise return the most recent pressure read. This is done because calls to the pressure sensor
        are somewhat slow.

        Additionally, the pressure sensor may raise I/O or Runtime errors intermittently.

        To mitigate a crash if that is the case, we attempt to read the
        pressure sensor a few times until a valid value is returned. If a valid value is not received
        after `max_attempts`, then a -1 flag is returned.
        """

        if perf_counter() - self.prev_poll_time_s > self.polling_time_s:
            if self.mpr_enabled:
                max_attempts = 6
                while max_attempts > 0:
                    try:
                        new_pressure = self.mpr.pressure
                        self.prev_pressure = new_pressure
                        self.prev_poll_time_s = perf_counter()
                        return new_pressure
                    except IOError:
                        max_attempts -= 1
                    except RuntimeError:
                        max_attempts -= 1
                self.io_error_counter += 1
                return INVALID_READ_FLAG
            else:
                raise PressureSensorNotInstantiated(self.mpr_err_msg)
        else:
            return self.prev_pressure

    def isMovePossible(self, move_dir: SyringeDirection) -> bool:
        """Return true if the syringe can still move in the specified direction."""

        # Cannot move the syringe up
        if self.duty_cycle > self.max_duty_cycle and move_dir == SyringeDirection.UP:
            return False

        # Cannot move the syringe down
        elif (
            self.duty_cycle < self.min_duty_cycle and move_dir == SyringeDirection.DOWN
        ):
            return False

        return True
