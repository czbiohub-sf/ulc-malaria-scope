"""
The malaria scope object, containing all the different hardware
periperhals which make up the malaria scope.

Components
    - Motorcontroller (DRV8825 Nema)
    - Camera (Basler / AVT)
    - Pneumatic module (pressure sensor + servo)
    - LED (TPS54201DDCT driver)
    - Cooling fans
    - Rotary encoder
    - Real time clock (PCF8523)
    - Temperature/humidity sensor (SHT31-D)
"""

import logging
import enum

from time import sleep
from typing import Dict, Optional

from ulc_mm_package.hardware.hardware_modules import *
from ulc_mm_package.scope_constants import SIMULATION, CAMERA_SELECTION, CameraOptions
from ulc_mm_package.image_processing.data_storage import DataStorage, DataStorageError
from ulc_mm_package.neural_nets.neural_network_modules import TPUError, AutoFocus, YOGO


class Components(enum.Enum):
    MOTOR = 0
    CAMERA = 1
    PNEUMATIC_MODULE = 2
    LED = 3
    FAN = 4
    ENCODER = 5
    HT_SENSOR = 6
    DATA_STORAGE = 7
    TPU = 8


class MalariaScope:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.motor_enabled = False
        self.camera_enabled = False
        self.pneumatic_module_enabled = False
        self.led_enabled = False
        self.fan_enabled = False
        self.encoder_enabled = False
        self.ht_sensor_enabled = False
        self.data_storage_enabled = False
        self.tpu_enabled = False

        # Initialize Components
        self._init_motor()
        self._init_camera()
        self._init_pneumatic_module()
        self._init_led()
        self._init_fan()
        self._init_encoder()
        self._init_humidity_temp_sensor()
        self._init_data_storage()
        self._init_TPU()

        self.logger.info("Initialized scope hardware.")

    def shutoff(self):
        self.logger.info("Shutting off scope hardware.")
        self.led.turnOff()
        self.pneumatic_module.setDutyCycle(self.pneumatic_module.getMaxDutyCycle())
        if self.camera._isActivated:
            self.camera.deactivateCamera()
            self.logger.info("Deactivated camera.")
        else:
            self.logger.info("Camera was not activated, no operations needed.")

    def getComponentStatus(self) -> Dict:
        """Returns a dictionary of component to initialization status.

        Can be used by the caller of MalariaScope to check that different
        components were initialized correctly (and take appropriate measures
        if not).
        """

        return {
            Components.MOTOR: self.motor_enabled,
            Components.CAMERA: self.camera_enabled,
            Components.PNEUMATIC_MODULE: self.pneumatic_module_enabled,
            Components.LED: self.led_enabled,
            Components.FAN: self.fan_enabled,
            Components.ENCODER: self.encoder_enabled,
            Components.HT_SENSOR: self.ht_sensor_enabled,
            Components.DATA_STORAGE: self.data_storage_enabled,
            Components.TPU: self.tpu_enabled,
        }

    def _init_motor(self):
        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema(steptype="Half")
            self.motor.homeToLimitSwitches()
            # print("Moving motor to the middle.")
            # sleep(0.5)
            # self.motor.move_abs(int(self.motor.max_pos // 2))
            self.motor_enabled = True
        except MotorControllerError as e:
            self.logger.error(f"DRV8825 initialization failed. {e}")

    def _init_camera(self):
        try:
            if CAMERA_SELECTION == CameraOptions.BASLER:
                self.camera = BaslerCamera()
                self.camera_enabled = True
            elif CAMERA_SELECTION == CameraOptions.AVT:
                self.camera = AVTCamera()
                self.camera_enabled = True
            elif SIMULATION:
                # just choose AVT, the import will be overridden w/ the simulated class
                self.camera = AVTCamera()
                self.camera_enabled = True
            else:
                raise CameraError(
                    "Invalid camera selection - must be 0 (Basler) or 1 (AVT)"
                )
            self.camera_activated = True
        except CameraError as e:
            self.logger.error(f"Camera initialization failed. {e}")

    def _init_pneumatic_module(self):
        # Create pressure controller (sensor + servo)
        try:
            self.pneumatic_module = PneumaticModule()

            # Check to see if the pressure sensor was successfully instantiated
            if not self.pneumatic_module.mpr_enabled:
                # If pressure sensor not created, raises PressureSensorNotInstantiated error
                # when calling `pneumatic_module.getPressure()`
                self.logger.error(
                    f"Pressure sensor initialization failed. {self.pneumatic_module.mpr_err_msg}"
                )

            self.pneumatic_module_enabled = True
        except PneumaticModuleError as e:
            self.logger.error(f"Pressure controller initialization failed. {e}")

    def _init_led(self):
        # Create the LED
        try:
            self.led = LED_TPS5420TDDCT()
            self.led.turnOn()
            self.led.setDutyCycle(0)
            self.led_enabled = True
        except LEDError as e:
            self.logger.error(f"LED driver initialization failed. {e}")

    def _init_fan(self):
        # Create and turn on the fans
        try:
            self.fan = Fan()
            self.fan.turn_on_all()
            self.fan_enabled = True
        except Exception as e:
            self.logger.error(f"Fan initialization failed. {e}")

    def _init_encoder(self):
        if self.motor_enabled:

            def manualFocusWithEncoder(self, increment: int):
                try:
                    if increment == 1:
                        self.motor.threaded_move_rel(dir=Direction.CW, steps=1)
                    elif increment == -1:
                        self.motor.threaded_move_rel(dir=Direction.CCW, steps=1)
                    sleep(0.01)
                    self.updateMotorPosition(self.motor.pos)
                except MotorControllerError:
                    self.encoder.setColor(255, 0, 0)
                    sleep(0.1)
                    self.encoder.setColor(12, 159, 217)

            # Connect the encoder
            try:
                self.encoder = PIM522RotaryEncoder(manualFocusWithEncoder)
                self.encoder_enabled = True
            except EncoderI2CError as e:
                self.logger.error(f"Encoder I2C initialization failed. {e}")
        else:
            self.logger.error(
                f"Motor initialization failed, so encoder will not initialize."
            )

    def _init_humidity_temp_sensor(self):
        try:
            self.ht_sensor = SHT3X()
            self.ht_sensor_enabled = True
        except Exception as e:
            self.logger.error(f"Temperature/humidity sensor initialization failed. {e}")

    def _init_data_storage(self, fps_lim: Optional[float] = None):
        try:
            self.data_storage = DataStorage(default_fps=fps_lim)
            self.data_storage_enabled = True
        except DataStorageError as e:
            self.logger.error(f"Data storage initialization failed. {e}")

    def _init_TPU(self):
        try:
            self.autofocus_model = AutoFocus()
            self.cell_diagnosis_model = YOGO()
            self.tpu_enabled = True
        except TPUError as e:
            self.logger.error(f"TPU initialization failed. {e}")
