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
import pigpio
import board
import adafruit_mprls

import numpy as np
from ulc_mm_package.hardware.hardware_constants import *
from ulc_mm_package.image_processing.flowrate import FlowRateEstimator

INVALID_READ_FLAG = -1
TOL_hPa = 1
DEFAULT_AFC_DELAY_S = 10

class PressureControlError(Exception):
    """Base class for catching all pressure control related errors."""
    pass

class PressureSensorNotInstantiated(PressureControlError):
    """Raised when the Adafruit MPRLS can not be instantiated."""
    def __init__(self):
        super().__init__("Could not instantiate pressure sensor.")

class PressureLeak(PressureControlError):
    """Raised when a pressure leak is detected."""
    def __init__(self):
        super().__init__("Pressure leak detected.")

class PressureControl():
    """Class that deals with monitoring and adjusting the pressure. 

    Interfaces with an Adafruit MPRLS pressure sensor to get the readings (valid for 0-25 bar). Uses a
    PWM-driven Servo motor (Pololu HD-1810MG) to adjust the position of the syringe (thereby adjusting the pressure).
    """
    def __init__(self, servo_pin: int=SERVO_PWM_PIN, pi: pigpio.pi=None):
        self._pi = pi if pi != None else pigpio.pi()
        self.servo_pin = servo_pin

        self.min_step_size = 10
        self.min_duty_cycle = 1600
        self.max_duty_cycle = 2200
        self.duty_cycle = self.max_duty_cycle
        self.prev_duty_cycle = self.duty_cycle
        self.prev_pressure = 0
        self.io_error_counter = 0
        self.prev_time_s = 0
        self.control_delay_s = 0.2

        # Active flow control variables
        self.flowrate_target = 0
        self.prev_afc_time_s = 0
        self.afc_delay_s = DEFAULT_AFC_DELAY_S

        # Toggle 5V line
        self._pi.write(SERVO_5V_PIN, 1)
        
        # Move servo to default position (minimum, stringe fully extended out)
        self._pi.set_pull_up_down(servo_pin, pigpio.PUD_DOWN)
        self._pi.set_servo_pulsewidth(servo_pin, self.duty_cycle)

        # Instantiate pressure sensor
        try:
            i2c = board.I2C()
            self.mpr = adafruit_mprls.MPRLS(i2c, psi_min=0, psi_max=25)
        except Exception:
            raise PressureSensorNotInstantiated()

    def close(self):
        """Move the servo to its lowest-pressure position and close."""
        self.setDutyCycle(self.max_duty_cycle)
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
            sleep(0.01)

    def decreaseDutyCycle(self):
        if self.duty_cycle >= self.min_duty_cycle + self.min_step_size:
            self.duty_cycle -= self.min_step_size
            self._pi.set_servo_pulsewidth(self.servo_pin, self.duty_cycle)
            sleep(0.01)

    def setDutyCycle(self, duty_cycle: int):
        if self.min_duty_cycle <= duty_cycle <= self.max_duty_cycle:
            if self.duty_cycle < duty_cycle:
                while self.duty_cycle <= duty_cycle - self.min_step_size:
                    self.increaseDutyCycle()
            else:
                while self.duty_cycle >= duty_cycle + self.min_step_size:
                    self.decreaseDutyCycle()
    
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

    def getPressure(self, apc_on: bool=False):
        """The pressure sensor is not always reliable. It may raise I/O or Runtime
        errors intermittently.

        To mitigate a crash if that is the case, we attempt to read the 
        pressure sensor a few times until a valid value is returned. If a valid value is not received
        after `max_attempts`, then a -1 flag is returned. 
        """
        
        if apc_on:
            return self.curr_pressure
        else:
            return self._getPressure()

    def _getPressure(self):
        max_attempts = 6
        while max_attempts > 0:
            try:
                return self.mpr.pressure
            except IOError:
                max_attempts -= 1
            except RuntimeError:
                max_attempts -= 1
        self.io_error_counter += 1
        return INVALID_READ_FLAG

    def isPressureReadValid(self, pressure: float) -> bool:
        if pressure < 0:
            return False
        return True

    def pressureWithinTol(self, pressure: float, target_pressure: float) -> bool:
        if abs(target_pressure-pressure) < TOL_hPa:
            return True
        return False

    def isLeak(self, pressure: float, target_pressure: float) -> bool:
        """
        If the current pressure is not at or near the target pressure
        and there is no additional room for the syringe to move, then 
        some vacuum has been lost.
        """
        if not self.pressureWithinTol(pressure, target_pressure):
            if self.duty_cycle == self.max_duty_cycle and target_pressure > pressure:
                return True
            elif self.duty_cycle == self.min_duty_cycle and target_pressure < pressure:
                return True
            return False

    def holdPressure(self, target_pressure: float):
        # Limit the polling frequency
        if perf_counter() - self.prev_time_s < self.control_delay_s:
            return

        self.curr_pressure = self.getPressure()

        if self.isPressureReadValid(self.curr_pressure):
            if self.pressureWithinTol(self.curr_pressure, target_pressure):
                return

            diff = target_pressure - self.curr_pressure
            if diff > 0:
                self.increaseDutyCycle()
            elif diff < 0:
                self.decreaseDutyCycle()
            else:
                return
            new_pressure = self.getPressure()
            if self.isPressureReadValid(new_pressure):
                new_diff = target_pressure - new_pressure
                if abs(diff) < abs(new_diff) and diff > 0:
                    self.decreaseDutyCycle()
                elif abs(diff) < abs(new_diff) and diff < 0:
                    self.increaseDutyCycle()
            self.prev_time_s = perf_counter()
            if self.isLeak(self.curr_pressure, target_pressure):
                raise PressureLeak

    def initializeActiveFlowControl(self, img: np.ndarray):
        """Initialize the FlowRateEstimator with the correct image shape."""
        h, w = img.shape
        self.fre = FlowRateEstimator(h, w, num_image_pairs=12)
        self.flowrate_target = None

    def activeFlowControl(self, img: np.ndarray):
        # Step 1 - continuously acquire images to set the desired flow rate
        if self.flowrate_target == None:
            self.fre.addImageAndCalculatePair(img, perf_counter())
            if self.fre.isFull():
                _, self.flowrate_target, _, _, _, _ = self.fre.getStatsAndReset()

        # Step 2. Check flow periodically
        else:
            if perf_counter() - self.prev_afc_time_s > self.afc_delay_s:
                if not self.fre.isFull():
                    self.fre.addImageAndCalculatePair(img, perf_counter())
                else:
                    dx, dy, _, _, _, _ = self.fre.getStatsAndReset()
                    flow_err = self.getFlowrateError(self.flowrate_target, dy)
                    self.adjustPressure(flow_err)

    def isMovePossible(self, move_dir: int) -> bool:
        """Return true if the syringe can still move in the specified direction."""
        
        # Cannot move the syringe up
        if self.duty_cycle == self.max_duty_cycle and move_dir == 1:
                return False
                
        # Cannot move the syringe down
        elif self.duty_cycle == self.min_duty_cycle and move_dir == -1:
            return False

        return True

    def adjustPressure(self, flow_diff: float):
        """Adjust the syringe position based on the flow rate error.

        If the actual flow rate is not the target and the syringe is already at the limit of its motion,
        this function raises a "PressureLeak()" error.
        """

        if flow_diff < 0:
            if self.isMovePossible(move_dir=-1):
                self.decreaseDutyCycle()
                self.afc_delay_s = 0.1
            else:
                raise PressureLeak()

        elif flow_diff > 0:
            if self.isMovePossible(move_dir=1):
                self.increaseDutyCycle()
                self.afc_delay_s = 0.1
            else:
                raise PressureLeak()

        else:
            self.afc_delay_s = DEFAULT_AFC_DELAY_S

    def getFlowrateError(self, desired_flowrate: float, current_flowrate: float, noiseTolPerc: float=0.05) -> float:
        """Returns the difference between the target and current flowrate, if the difference is above a noise tolerance."""

        error = desired_flowrate - current_flowrate
        if error/desired_flowrate <= noiseTolPerc:
            return 0
        return error

    def pid(self, error: float, prev_error: float, p: int=5, i: int=0, d: int=0):
        pidGain = (p*error) + (i*error + i) + (d*(error - prev_error))
        print(pidGain)