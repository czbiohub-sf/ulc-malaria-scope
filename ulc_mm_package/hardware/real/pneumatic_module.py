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
import configparser
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor
import logging

import pigpio
import board
import adafruit_mprls

from ulc_mm_package.scope_constants import CONFIGURATION_FILE
from ulc_mm_package.utilities.lock_utils import lock_no_block
from ulc_mm_package.hardware.hardware_constants import (
    SERVO_5V_PIN,
    SERVO_PWM_PIN,
    SERVO_FREQ,
    STALE_PRESSURE_VAL_TIME_S,
    MPRLS_RST,
    MPRLS_PWR,
    DEFAULT_SYRINGE_MAX_DUTY_CYCLE,
    DEFAULT_SYRINGE_MIN_DUTY_CYCLE,
    DEFAULT_STEP,
)
from ulc_mm_package.hardware.dtoverlay_pwm import (
    dtoverlay_PWM,
    PWM_CHANNEL,
)
from ulc_mm_package.hardware.pneumatic_module import (
    PressureSensorNotInstantiated,
    InvalidConfigurationParameters,
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
        pi: pigpio.pi = None,
    ):
        self.logger = logging.getLogger(__name__)
        self._pi = pi if pi is not None else pigpio.pi()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.servo_pin = servo_pin

        # Load configuration file parameters
        (
            self.min_duty_cycle,
            self.max_duty_cycle,
            self.min_step_size,
        ) = self.get_config_params()

        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle

        # Toggle 5V line
        self._pi.write(SERVO_5V_PIN, 1)

        # Move servo to default position (minimum, stringe fully extended out)
        self._pi.set_pull_up_down(servo_pin, pigpio.PUD_DOWN)

        self.pwm = dtoverlay_PWM(PWM_CHANNEL.PWM1)
        self.pwm.setFreq(SERVO_FREQ)
        self.pwm.setDutyCycle(self.duty_cycle)

        # Pressure sensor
        self.mpr = AdafruitMPRLS()
        self.mpr_enabled = self.mpr.mpr_enabled

    def close(self):
        """Move the servo to its lowest-pressure position and close."""

        self.setDutyCycle(self.max_duty_cycle)
        sleep(0.5)
        self._pi.stop()
        self.pwm.setDutyCycle(0)
        sleep(0.5)

    def config_exists(self) -> bool:
        """Check for the existence of a configuration file."""
        if Path(CONFIGURATION_FILE).is_file():
            return True
        return False

    def get_config_params(self) -> Tuple[float, float, float]:
        """Returns min/max duty cycles for syringe position and step size from the configuration file if it exists."""
        if self.config_exists():
            config = configparser.ConfigParser()
            try:
                assert (
                    len(config.read(f"{CONFIGURATION_FILE}")) > 0
                ), f"configparser failed to read file {CONFIGURATION_FILE}."
                min_duty_cycle = float(config["SYRINGE"]["MIN_DUTY_CYCLE"])
                max_duty_cycle = float(config["SYRINGE"]["MAX_DUTY_CYCLE"])
                step_size = float(config["SYRINGE"]["DUTY_CYCLE_STEP"])

                if (
                    min_duty_cycle >= max_duty_cycle
                    or min_duty_cycle < 0
                    or max_duty_cycle > 1
                    or step_size < 0
                ):
                    raise InvalidConfigurationParameters(
                        f"Invalid configuration parameters. Min: {min_duty_cycle}, Max: {max_duty_cycle}, Step: {step_size}\n"
                        f"Min must be >= 0 and less than max_duty_cycle. Max must be <=1.0. Step size must be > 0"
                    )
                return min_duty_cycle, max_duty_cycle, step_size
            except Exception as e:
                self.logger.exception(
                    f"Error encountered while reading syringe min/max from the config file, {CONFIGURATION_FILE}. Setting defaults instead.\nException: {e}"
                )
                return (
                    DEFAULT_SYRINGE_MIN_DUTY_CYCLE,
                    DEFAULT_SYRINGE_MAX_DUTY_CYCLE,
                    DEFAULT_STEP,
                )
        else:
            self.logger.info(
                f"{CONFIGURATION_FILE} was not found, using default values instead for syringe min/max duty cycle."
            )
            return (
                DEFAULT_SYRINGE_MIN_DUTY_CYCLE,
                DEFAULT_SYRINGE_MAX_DUTY_CYCLE,
                DEFAULT_STEP,
            )

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

    def threadedDecreaseDutyCycle(self):
        if not SYRINGE_LOCK.locked():
            if not self.isMovePossible(SyringeDirection.DOWN):
                raise SyringeEndOfTravel()
            self.executor.submit(self.decreaseDutyCycle)
        else:
            raise SyringeInMotion

    def threadedIncreaseDutyCycle(self):
        if not SYRINGE_LOCK.locked():
            if not self.isMovePossible(SyringeDirection.UP):
                raise SyringeEndOfTravel()
            self.executor.submit(self.increaseDutyCycle)
        else:
            raise SyringeInMotion

    def threadedSetDutyCycle(self, *args, **kwargs):
        if not SYRINGE_LOCK.locked():
            self.executor.submit(self.setDutyCycle, *args, **kwargs)
        else:
            raise SyringeInMotion

    def isMovePossible(self, move_dir: SyringeDirection) -> bool:
        """Return true if the syringe can still move in the specified direction."""

        # Cannot move the syringe up
        if (
            self.duty_cycle + self.min_step_size > self.max_duty_cycle
            and move_dir == SyringeDirection.UP
        ):
            return False

        # Cannot move the syringe down
        elif (
            self.duty_cycle - self.min_step_size < self.min_duty_cycle
            and move_dir == SyringeDirection.DOWN
        ):
            return False

        return True

    @staticmethod
    def is_locked():
        return SYRINGE_LOCK.locked()

    def getPressure(self) -> Tuple[float, PressureSensorRead]:
        return self.mpr.getPressure()

    def getPressureImmediately(self) -> Tuple[float, PressureSensorRead]:
        return self.mpr.getPressureImmediately()

    def getPressureMaxReadAttempts(
        self, max_attempts: int = 10
    ) -> Tuple[float, PressureSensorRead]:
        return self.mpr.getPressureMaxReadAttempts(max_attempts)

    def direct_read(self) -> Tuple[float, PressureSensorRead]:
        return self.mpr.direct_read()


class AdafruitMPRLS:
    def __init__(
        self,
        mprls_rst_pin: int = MPRLS_RST,
        mprls_pwr_pin: int = MPRLS_PWR,
        pi: pigpio.pi = None,
    ):
        self.logger = logging.getLogger(__name__)
        self._pi = pi if pi is not None else pigpio.pi()
        self.mprls_rst_pin = mprls_rst_pin
        self.mprls_pwr_pin = mprls_pwr_pin
        self.prev_poll_time_s: float = 0.0
        self.prev_pressure: float = 0.0
        self.prev_status = PressureSensorRead.ALL_GOOD

        self.io_error_counter = 0
        self.mpr_enabled = False
        self.mpr_err_msg = ""

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
        self._pi.write(self.mprls_rst_pin, 0)
        sleep(0.005)
        self._pi.write(self.mprls_pwr_pin, 1)

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
        PressureSensorNotInstantiated:
            Raised if a read is attempted but the sensor was not instantiated successfully.

        PressureSensorStaleValue:
            If more than 'STALE_PRESSURE_VAL_TIME_S' has passed since the last read, this exception is raised, indicating
            that there might be something wrong with the sensor. This constant is defined in hardware_constants.py.
        """

        try:
            return self.getPressureImmediately()
        except PressureSensorBusy:
            if perf_counter() - self.prev_poll_time_s > STALE_PRESSURE_VAL_TIME_S:
                raise PressureSensorStaleValue(
                    f"{perf_counter() - self.prev_poll_time_s}s elapsed since last read (last value was: {self.prev_pressure} w/ status {self.prev_status.value})."
                )
            self.logger.info("Returning previous pressure value.")
            return self.prev_pressure, self.prev_status

    def getPressureImmediately(self) -> Tuple[float, PressureSensorRead]:
        """Attempt to read the pressure sensor immediately, raises an exception if sensor busy.

        This differs from `getPressure()` in that `getPressure()` will return the most recent
        value from the within the past `STALE_PRESSURE_VAL_TIME_S` seconds if the sensor is busy.
        This function will raise an exception immediately if the sensor is busy.

        Returns
        -------
        Tuple[float, PressureSensorRead]:
            float - pressure valuei.
            PressureSensorRead - enum which shows whether a status bit was funky when reading the pressure.

        Exceptions
        ----------
        PressureSensorNotInstantiated:
            Raised if a read is attempted but the sensor was not instantiated successfully.

        PressureSensorBusy:
            Raised when a read is attempted but the sensor is busy and unable to return a value right away.
        """

        if self.mpr_enabled:
            try:
                pressure, status = self.direct_read()
                self.prev_pressure, self.prev_status = pressure, status
                self.prev_poll_time_s = perf_counter()
                return (pressure, status)
            except PressureSensorBusy as e:
                self.logger.info(f"Attempted read but pressure sensor is busy: {e}.")
                raise PressureSensorBusy()
        else:
            raise PressureSensorNotInstantiated(self.mpr_err_msg)

    def getPressureMaxReadAttempts(
        self, max_attempts: int = 10
    ) -> Tuple[float, PressureSensorRead]:
        """Attempt to read the sensor `max_attempt` times before raising an exception.

        Parameters
        ----------
        max_attempts: int
            Maximum number of times to read the sensor before raising an exception.

        Exceptions
        ----------
        PressureSensorBusy:
            Raised if a value is unable to be read after max_attempts
        """
        while max_attempts <= 0:
            try:
                return self.getPressureImmediately()
            except PressureSensorBusy:
                max_attempts -= 1
                sleep(0.05)
        else:
            raise PressureSensorBusy(
                f"Failed to get a pressure sensor read after: {max_attempts} attempts."
            )

    def _direct_read(self, timeout_s: float = 1e6) -> bool:
        """Internal function - direct read of mprls buffer.

        Stores the read in an internal variable.

        Returns
        -------
        bool
            Whether the read was successful or not.
        """

        # Attempt to read the sensor first
        self.mpr._buffer[0] = 0xAA
        self.mpr._buffer[1] = 0
        self.mpr._buffer[2] = 0
        start = perf_counter()
        with self.mpr._i2c as i2c:
            # send command
            i2c.write(self.mpr._buffer, end=3)
            # ready busy flag/status
            while True:
                # check End of Convert pin first, if we can
                if self.mpr._eoc is not None:
                    if self.mpr._eoc.value:
                        break
                # or you can read the status byte
                i2c.readinto(self.mpr._buffer, end=1)
                if not self.mpr._buffer[0] & 0x20:
                    break

                # Breakout if pressure sensor is too slow
                if perf_counter() - start > timeout_s:
                    return False

            # no longer busy!
            i2c.readinto(self.mpr._buffer, end=4)
            return True

    def direct_read(self) -> Tuple[float, PressureSensorRead]:
        """Pressure sensor direct read.

        This pressure sensor has had a notorious track record of throwing Integrity Errors.
        Reading directly from the buffer shows that the actual pressure values are as expected.

        This function just bypasses the exceptions that are normally thrown by Adafruit's MPRLS library and
        returns the pressure value (in addition with an enum detailing if any exceptions were thrown.

        Returns
        -------
        Tuple[float, PressureSensorRead]:
            float - pressure
            PressureSensorRead - status bit (all good, saturation, or integrity error)

        Exceptions
        ----------
        PressureSensorBusy:
            Raised if sensor takes longer than the set time to respond
        """
        # Attempt to read, cap timeout at 0.5s
        timeout_s = 0.1
        read_success = self._direct_read(timeout_s=0.5)

        if not read_success:
            raise PressureSensorBusy(
                f"Pressure sensor took too long (>= {timeout_s}s) to respond."
            )

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
