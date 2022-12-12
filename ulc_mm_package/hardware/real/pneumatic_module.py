""" Adafruit MPRLS Ported Pressure Sensor Breakout Board and PWM Servo

-- Important Links --
Adafruit Product Page:
    https://www.adafruit.com/product/3965
Adafruit MPRLS Python Library:
    https://github.com/adafruit/Adafruit_CircuitPython_MPRLS
Servo Motor Pololu HD-1810MG:
    https://www.pololu.com/product/1047
"""

from time import sleep, perf_counter
from typing import Tuple
import threading
import enum
import logging

import pigpio
import board
import adafruit_mprls

from ulc_mm_package.utilities.lock_utils import lock_no_block
from ulc_mm_package.hardware.hardware_constants import (
    SERVO_5V_PIN,
    SERVO_PWM_PIN,
    SERVO_FREQ,
    STALE_PRESSURE_VAL_TIME_S,
    MPRLS_RST,
    MPRLS_PWR,
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
    PressureSensorBusy,
    PressureSensorStaleValue,
    PressureSensorRead,
)


SYRINGE_LOCK = threading.Lock()
PSI_TO_HPA = 68.947572932


class PneumaticModule:
    """Class that deals with monitoring and adjusting the pressure.

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """

    def __init__(
        self,
        servo_pin: int = SERVO_PWM_PIN,
        mprls_rst_pin: int = MPRLS_RST,
        mprls_pwr_pin: int = MPRLS_PWR,
        pi: pigpio.pi = None,
    ):
        self.logger = logging.getLogger(__name__)
        self._pi = pi if pi != None else pigpio.pi()
        self.servo_pin = servo_pin
        self.mprls_rst_pin = mprls_rst_pin
        self.mprls_pwr_pin = mprls_pwr_pin

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
        self.prev_status = PressureSensorRead.ALL_GOOD
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
        self._pi.write(self.mprls_pwr_pin, 0)
        sleep(0.005)
        self._pi.write(self.mprls_rst_pin, 1)
        sleep(0.005)

        try:
            i2c = board.I2C()
            self.mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)
            self.mpr_enabled = True
        except Exception as e:
            self.mpr_err_msg = f"{e}"
            self.mpr_enabled = False

    def close(self):
        """Move the servo to its lowest-pressure position and close."""
        self._pi.write(self.mprls_rst_pin, 0)
        sleep(0.005)
        self._pi.write(self.mprls_pwr_pin, 1)

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

    @lock_no_block(SYRINGE_LOCK, SyringeInMotion)
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

    def getPressure(self) -> Tuple[float, PressureSensorRead]:
        """Attempt to read the pressure sensor. Return pressure and status.

        If a read is done while the pressure sensor is busy, the previous value will be returned.
        If more than 'STALE_PRESSURE_VAL_TIME_S' has elapsed since the last read, an exception is raised.

        Returns
        -------
        Tuple[float, PressureSensorRead]:
            float - pressure valuei.
            PressureSensorRead - enum which shows whether a status bit was funky when reading the pressure.

        Exceptions
        ----------
        PressureSensorStaleValue:
            If more than 'STALE_PRESSURE_VAL_TIME_S' has passed since the last read, this exception is raised, indicating
            that there might be something wrong with the sensor. This constant is defined in hardware_constants.py.
        """

        if self.mpr_enabled:
            try:
                pressure, status = self.direct_read()
                self.prev_pressure, self.prev_status = pressure, status
                return (pressure, status)
            except PressureSensorBusy as e:
                self.logger.info(
                    f"Attempted read but pressure sensor is busy: {e}. Returning previous pressure value."
                )
                if perf_counter() - self.prev_poll_time_s > STALE_PRESSURE_VAL_TIME_S:
                    raise PressureSensorStaleValue(
                        f"{perf_counter() - self.prev_poll_time_s}s elapsed since last read (last value was: {self.prev_pressure} w/ status {self.prev_status.value})."
                    )
                return self.prev_pressure, self.prev_status
        else:
            raise PressureSensorNotInstantiated(self.mpr_err_msg)

    def _direct_read(self) -> bool:
        """Attempt to read the pressure sensor status and 24-bit data reading into the buffer.

        Returns
        -------
        bool:
            True if read successful

        Exceptions
        ----------
        PressureSensorBusy
        """

        self.mpr._buffer[0] = 0xAA
        self.mpr._buffer[1] = 0
        self.mpr._buffer[2] = 0
        with self.mpr._i2c as i2c:
            # send command
            i2c.write(self.mpr._buffer, end=3)

            # Check if sensor busy

            # check End of Convert pin first, if we can
            if self.mpr._eoc is not None:
                if not self.mpr._eoc.value:
                    raise PressureSensorBusy(
                        "Pressure sensor is currently busy. I've got a life too y'know?"
                        "'self.mpr._eoc.value' is False (which is why this exception was raised)."
                    )
            # or you can read the status byte
            i2c.readinto(self.mpr._buffer, end=1)
            if self.mpr._buffer[0] & 0x20:
                raise PressureSensorBusy(
                    "Pressure sensor is currently busy. I've got a life too y'know?"
                    "Status byte, 'self.mpr._buffer[0] & 0x20' returned True (which is why this exception was raised)."
                )

            # Otherwise sensor is ok to read
            i2c.readinto(self.mpr._buffer, end=4)
            return True

    def direct_read(self) -> Tuple[float, PressureSensorRead]:
        """Pressure sensor direct read.

        This pressure sensor has had a notorious track record of throwing Integrity Errors.
        Reading directly from the buffer shows that the actual pressure values are as expected.

        This function just bypasses the exceptions that are normally thrown by Adafruit's MPRLS library and
        returns the pressure value (in addition with an enum detailing if any exceptions were thrown.
        """

        # Attempt to read the sensor first
        try:
            read_success = self._direct_read()
        except PressureSensorBusy as e:
            raise PressureSensorBusy(e)

        # If read successful, check status flags
        if read_success:
            error_flag = PressureSensorRead.ALL_GOOD
            # check other status bits
            if self.mpr._buffer[0] & 0x01:
                error_flag = PressureSensorRead.SATURATION
            if self.mpr._buffer[0] & 0x04:
                error_flag = PressureSensorRead.INTEGRITY

            # Calculate and return pressure
            ##### Code below from Adafruit's MPRLS library! #####
            raw_psi = (
                (self.mpr._buffer[1] << 16)
                | (self.mpr._buffer[2] << 8)
                | self.mpr._buffer[3]
            )
            # use the 10-90 calibration curve
            psi = (raw_psi - 0x19999A) * (self.mpr._psimax - self.mpr._psimin)
            psi /= 0xE66666 - 0x19999A
            psi += self.mpr._psimin

            # convert PSI to hPA
            return (psi * PSI_TO_HPA, error_flag)

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
