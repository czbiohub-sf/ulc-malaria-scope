"""
The malaria scope object, containing all the different hardware
periperhals which make up the malaria scope.

Components
    - Motorcontroller (DRV8825 Nema)
    - Camera (Basler / AVT)
    - Pneumatic module (pressure sensor + servo)
    - LED (TPS54201DDCT driver)
    - Cooling fans
    - Rotary encoder (disabled for now)
    - Real time clock (PCF8523)
    - Temperature/humidity sensor (SHT31-D)
"""

import logging
from enum import Enum, auto
from time import sleep
from typing import Dict, Optional, Callable

import pigpio

from ulc_mm_package.hardware.hardware_constants import LID_LIMIT_SWITCH2, CAMERA_FPS

from ulc_mm_package.hardware.camera import BaslerCamera, AVTCamera, CameraError
from ulc_mm_package.hardware.motorcontroller import (
    DRV8825Nema,
    Direction,
    MotorControllerError,
)
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError
from ulc_mm_package.hardware.pim522_rotary_encoder import (
    PIM522RotaryEncoder,
    EncoderI2CError,
)
from ulc_mm_package.hardware.pneumatic_module import (
    PneumaticModule,
    PneumaticModuleError,
    SyringeInMotion,
)
from ulc_mm_package.hardware.fan import Fan
from ulc_mm_package.hardware.sht31d_temphumiditysensor import SHT3X
from ulc_mm_package.scope_constants import SIMULATION, CAMERA_SELECTION, CameraOptions
from ulc_mm_package.image_processing.data_storage import DataStorage, DataStorageError
from ulc_mm_package.image_processing.flow_control import FlowController
from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus
from ulc_mm_package.neural_nets.NCSModel import TPUError
from ulc_mm_package.neural_nets.predictions_handler import PredictionsHandler


class GPIOEdge(Enum):
    RISING_EDGE = 0
    FALLING_EDGE = 1
    EITHER_EDGE = 2


class Components(Enum):
    MOTOR = auto()
    CAMERA = auto()
    PNEUMATIC_MODULE = auto()
    PRESSURE_SENSOR = auto()
    LED = auto()
    FAN = auto()
    ENCODER = auto()
    HT_SENSOR = auto()
    DATA_STORAGE = auto()
    FLOW_CONTROLLER = auto()
    TPU = auto()
    PREDICTIONS_HANDLER = auto()


class MalariaScope:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.motor_enabled = False
        self.camera_enabled = False
        self.pneumatic_module_enabled = False
        self.pressure_sensor_enabled = False
        self.led_enabled = False
        self.fan_enabled = False
        self.ht_sensor_enabled = False
        self.data_storage_enabled = False
        self.flow_controller_enabled = False
        self.tpu_enabled = False
        self.predictions_handler_enabled = False

        # Initialize Components
        self._init_motor()
        self._init_camera()
        self._init_pneumatic_module()
        self._init_led()
        self._init_fan()
        self._init_humidity_temp_sensor()
        self._init_data_storage()
        self._init_flow_controller()
        self._init_TPU()
        self._init_predictions_handler()

        self.logger.info("Initialized scope hardware.")

    def reset_pneumatic_and_led_and_flow_control(self) -> None:
        """Set the syringe to its top most position, turn the LED off, reset flow control variables."""
        self.logger.info(
            "Resetting pneumatic module, turning LED off, and flow control constants"
        )

        # Return pneumatic module to topmost position
        while self.pneumatic_module.is_locked():
            sleep(0.1)

        try:
            self.pneumatic_module.setDutyCycle(self.pneumatic_module.getMaxDutyCycle())
        except SyringeInMotion:
            # This should not happen
            self.logger.warning("Did not return syringe to top-most position!")

        # Turn off LED
        self.led.turnOff()

        # Resetting flow_controller parameters
        self.flow_controller.reset()

    def reset_for_end_experiment(self) -> None:
        """Reset syringe, turn LED off, reset flow control, and close data storage."""

        # Reset syringe to top, turn LED off, reset flow control variables
        self.reset_pneumatic_and_led_and_flow_control()

        # Close data storage
        closing_file_future = self.data_storage.close(
            self.predictions_handler.get_prediction_tensors()
        )
        if closing_file_future is not None:
            while not closing_file_future.done():
                sleep(1)

        # Reset predictions handler
        self.predictions_handler: PredictionsHandler = PredictionsHandler()

    def shutoff(self):
        self.logger.info("Shutting off scope hardware.")
        self.led.turnOff()
        self.pneumatic_module.setDutyCycle(self.pneumatic_module.getMaxDutyCycle())
        self.ht_sensor.stop()
        self.flow_controller.stop()
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
            Components.PRESSURE_SENSOR: self.pressure_sensor_enabled,
            Components.LED: self.led_enabled,
            Components.FAN: self.fan_enabled,
            Components.HT_SENSOR: self.ht_sensor_enabled,
            Components.DATA_STORAGE: self.data_storage_enabled,
            Components.FLOW_CONTROLLER: self.flow_controller_enabled,
            Components.TPU: self.tpu_enabled,
            Components.PREDICTIONS_HANDLER: self.predictions_handler_enabled,
        }

    def _init_motor(self):
        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema()
            self.motor.homeToLimitSwitches()
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
                self.camera.camera.AcquisitionFrameRateEnable.set(True)
                self.camera.camera.AcquisitionFrameRate.set(CAMERA_FPS)
                self.camera_enabled = True
            elif CAMERA_SELECTION == CameraOptions.SIMULATED:
                # just choose AVT, the import will be overridden w/ the simulated class
                self.camera = AVTCamera()
                self.camera_enabled = True
            elif CAMERA_SELECTION == CameraOptions.NONE:
                raise CameraError(
                    "Camera selection is set to NONE, but camera is being initialized. "
                    "A camera was not detected and this is not being run in simulation mode. "
                    "To run in simulation mode, run with MS_SIMULATE=1."
                )
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
                    f"Pressure sensor initialization failed. {self.pneumatic_module.mpr.mpr_err_msg}"
                )
                self.pressure_sensor_enabled = False
            else:
                self.pressure_sensor_enabled = True

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

            def manualFocusWithEncoder(increment: int):
                try:
                    if increment == 1:
                        self.motor.threaded_move_rel(dir=Direction.CW, steps=1)
                    elif increment == -1:
                        self.motor.threaded_move_rel(dir=Direction.CCW, steps=1)
                    sleep(0.01)
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
                "Motor initialization failed, so encoder will not initialize."
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

    def _init_flow_controller(self):
        try:
            self.flow_controller = FlowController(
                self.pneumatic_module,
                CAMERA_SELECTION.IMG_HEIGHT,
                CAMERA_SELECTION.IMG_WIDTH,
            )
            self.flow_controller_enabled = True
        except Exception as e:
            self.logger.error(f"Flow controller initialization failed. {e}")

    def _init_predictions_handler(self):
        try:
            self.predictions_handler = PredictionsHandler()
            self.predictions_handler_enabled = True
        except Exception as e:
            self.logger.error(f"PredictionsHandler initialization failed. {e}")

    def set_gpio_callback(
        self,
        callback_func: Callable,
        interrupt_pin: int = LID_LIMIT_SWITCH2,
        edge: GPIOEdge = GPIOEdge.RISING_EDGE,
        glitch_filer_us: int = 5000,
    ):
        """Set a callback to run when the given interrupt pin is triggered.

        Parameters
        ----------
        callback_func: Callable
            Function to call when the interrupt is triggered.
        interrupt_pin: int=15
            Defaults to the lid limit switch.
        edge: GPIOEdge
        glitch_filer_us: int
            Number of microseconds that a GPIO level change needs to stay steady for
            before a level change is reported (this is meant for debouncing)
        """

        if not SIMULATION:
            import pigpio  # Not the cleanest way to do this

            pi = pigpio.pi()
            pi.set_glitch_filter(interrupt_pin, glitch_filer_us)
            pi.callback(interrupt_pin, edge.value, callback_func)
            self.logger.info(
                f"Set callback on pin: {interrupt_pin} w/ debounce time of {glitch_filer_us} us."
            )
        else:
            self.logger.info("We're simulating, no callback set.")

    @staticmethod
    def read_lim_sw(pin: int = LID_LIMIT_SWITCH2):
        pi = pigpio.pi()
        return pi.read(LID_LIMIT_SWITCH2)
