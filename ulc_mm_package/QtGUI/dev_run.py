import cv2

from ulc_mm_package.QtGUI.gui_constants import FLOWCELL_QC_FORM_LINK
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT

from ulc_mm_package.scope_constants import (
    LOCKFILE,
    SSD_DIR,
    VIDEO_PATH,
    VIDEO_REC,
    SIMULATION,
)
from ulc_mm_package.hardware.scope import MalariaScope, Components

from ulc_mm_package.hardware.motorcontroller import (
    Direction,
    MotorControllerError,
    MotorInMotion,
)
from ulc_mm_package.hardware.led_driver_tps54201ddct import LEDError
from ulc_mm_package.hardware.pim522_rotary_encoder import EncoderI2CError
from ulc_mm_package.hardware.pneumatic_module import (
    PneumaticModule,
    PneumaticModuleError,
    PressureSensorNotInstantiated,
    SyringeInMotion,
    SyringeEndOfTravel,
    PressureSensorStaleValue,
)

from ulc_mm_package.hardware.scope_routines import Routines

from ulc_mm_package.image_processing.autobrightness import (
    BrightnessTargetNotAchieved,
    BrightnessCriticallyLow,
    LEDNoPower,
)
from ulc_mm_package.image_processing.flow_control import (
    FlowController,
    CantReachTargetFlowrate,
    LowConfidenceCorrelations,
)
from ulc_mm_package.image_processing.zstack import (
    full_sweep_image_collection,
    local_sweep_image_collection,
)

from ulc_mm_package.neural_nets.neural_network_constants import IMG_RESIZED_DIMS

from ulc_mm_package.image_processing.processing_constants import FLOWRATE

from ulc_mm_package.utilities.ngrok_utils import make_tcp_tunnel, NgrokError
from ulc_mm_package.utilities.email_utils import send_ngrok_email

from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus
import ulc_mm_package.neural_nets.neural_network_constants as nn_constants

import os
import sys
import traceback
import numpy as np
import webbrowser
import subprocess

from typing import Dict
from time import perf_counter, sleep
from os import listdir, path
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, uic  # type: ignore
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from qimage2ndarray import gray2qimage
from gpiozero import CPUTemperature

cpu = CPUTemperature()

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# Qt GUI Files
_UI_FILE_DIR = "dev_run.ui"


class ApplicationError(Exception):
    """Catch-all exception for misc errors not caught by the peripheral classes."""

    pass


class AcquisitionThread(QThread):
    # Qt signals must be defined at the class-level (not instance-level)
    changePixmap = pyqtSignal(QImage)
    motorPosChanged = pyqtSignal(int)
    zStackFinished = pyqtSignal(int)
    updatePressure = pyqtSignal(float)
    measurementTime = pyqtSignal(int)
    fps = pyqtSignal(int)
    temperatures = pyqtSignal(int)
    pressureLeakDetected = pyqtSignal(int)
    syringePosChanged = pyqtSignal(int)
    flowValChanged = pyqtSignal(float)
    autobrightnessDone = pyqtSignal(int)
    doneSaving = pyqtSignal(int)

    def __init__(self, external_dir, mscope: MalariaScope):
        super().__init__()
        self.mscope = mscope
        self._initializeAttributes(external_dir, mscope)
        if mscope.getComponentStatus()[Components.CAMERA]:
            self.camera = mscope.camera
            self.camera_activated = True
        else:
            self.camera_activated = False

    def _initializeAttributes(self, external_dir: str, mscope: MalariaScope):
        """Initialize attributes (variables, flags, references to hardware peripherals)
        in this function to make the __init__ more readable."""

        # Flags and counters
        self.im_counter = 0
        self.update_liveview = 1
        self.update_counter = 0
        self.num_loops = 50
        self.camera_activated = False
        self.main_dir = None
        self.single_save = False
        self.continuous_save = False
        self.liveview = True
        self.takeZStack = False
        self.custom_image_prefix = ""
        self.updateMotorPos = True
        self.updateSyringePos = True
        self.fps_timer = perf_counter()
        self.start_time = perf_counter()
        self.external_dir = external_dir
        self.click_to_advance = False
        self.finish_saving_future = None

        # Hardware peripherals
        self.motor = mscope.motor
        self.pneumatic_module: PneumaticModule = mscope.pneumatic_module
        mscope._init_data_storage(fps_lim=40)
        self.data_storage = mscope.data_storage

        # Routines
        self.routines = Routines()
        mscope.flow_controller.reset()
        self.flow_controller: FlowController = mscope.flow_controller
        self.initializeFlowControl = False
        self.flowcontrol_enabled = False
        self.fast_flow_enabled = False
        self.autobrightness = self.routines.autobrightnessRoutine(mscope)
        self.autobrightness_on = False
        self.timestamp = 0

        # Single-shot autofocus
        try:
            self.autofocus_model = AutoFocus()
        except RuntimeError as e:
            raise RuntimeError(
                f'got {str(e)}:\n {subprocess.getoutput("lsusb | grep Myriad")}'
            )
        self.active_autofocus = False
        self.prev_autofocus_time = 0.0
        self.af_adjustment_done = False

    def run(self):
        while True:
            if self.camera_activated:
                try:
                    for image, timestamp in self.camera.yieldImages():
                        self.timestamp = timestamp
                        self.updateGUIElements()
                        self.save(image)
                        self.zStack(image)
                        self.activeFlowControl(image)
                        self._autobrightness(image)
                        self.autofocusWrapper(image)

                        if self.liveview:
                            if self.update_counter % self.update_liveview == 0:
                                qimage = gray2qimage(image)
                                self.changePixmap.emit(qimage)
                        elif self.click_to_advance:
                            qimage = gray2qimage(image)
                            self.changePixmap.emit(qimage)
                            self.click_to_advance = False
                except Exception as e:
                    # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                    # Once that happens, this can be swapped to catch the PyCameraException
                    print(e)
                    print(traceback.format_exc())

    def getMetadata(self) -> Dict:
        """Required metadata:
        - Measurement type (actual diagnostic experiment or data collection)
        - Sample type / sample name (i.e dataset name)
        - Timestamp
        - Motor position
        - Syringe position
        - Pressure reading
        - Ambient temperature (updated every N Frames)
        - RPi CPU temperature (updated every N frames)
        - Focus metric (updated every N frames)
        - LED power
        """

        try:
            pressure, pressure_sensor_status = self.pneumatic_module.getPressure()
        except PressureSensorNotInstantiated:
            # TODO: Add logging
            pressure = -1
            pressure_sensor_status = -1
        except PressureSensorStaleValue as e:
            # TODO: Add logging
            print(f"Stale value from pressure sensor: {e}")
            pressure = -1
            pressure_sensor_status = -1

        return {
            "im_counter": self.im_counter,
            "measurement_type": "placeholder",
            "sample_type": "placeholder",
            "timestamp": self.timestamp,
            "exposure": self.camera.exposureTime_ms,
            "motor_pos": self.motor.pos,
            "pressure_hpa": pressure,
            "pressure_status_flag": pressure_sensor_status.value,
            "syringe_pos": self.pneumatic_module.getCurrentDutyCycle(),
            "flow_control_on": self.flowcontrol_enabled,
            "target_flowrate": self.flow_controller.target_flowrate,
            "current_flowrate": self.flow_controller.flowrate,
            "focus_adjustment": self.af_adjustment_done,
        }

    def save(self, image):
        if self.single_save:
            self.data_storage.writeSingleImage(image, self.custom_image_prefix)
            self.single_save = False

        if self.continuous_save:
            if self.data_storage.is_writable():
                self.data_storage.writeData(image, self.getMetadata(), self.im_counter)
                self.measurementTime.emit(int(perf_counter() - self.start_time))
                self.im_counter += 1

    def updateGUIElements(self):
        self.update_counter += 1
        if self.updateMotorPos:
            self.motorPosChanged.emit(self.motor.pos)

        if self.updateSyringePos:
            self.syringePosChanged.emit(1)

        if self.update_counter % self.num_loops == 0:
            self.update_counter = 0
            if self.pneumatic_module is not None:
                try:
                    # TODO: do something with the status
                    (
                        pressure,
                        pressure_sensor_status,
                    ) = self.pneumatic_module.getPressure()
                    self.updatePressure.emit(pressure)
                except Exception:
                    pressure = -1
                    self.updatePressure.emit(pressure)
            self.fps.emit(int(self.num_loops / (perf_counter() - self.fps_timer)))
            self.fps_timer = perf_counter()

            # Update temperatures
            self.temperatures.emit(1)

        if self.finish_saving_future is not None:
            if self.finish_saving_future.done():
                self.doneSaving.emit(1)
                self.finish_saving_future = None

    def updateExposure(self, exposure):
        self.camera.exposureTime_ms = exposure

    def takeImage(self):
        if self.main_dir is None:
            self.data_storage.createTopLevelFolder(
                self.external_dir, datetime.now().strftime(DATETIME_FORMAT)
            )
            self.main_dir = self.data_storage.main_dir

        if self.continuous_save:
            self.data_storage.createNewExperiment(
                self.external_dir,
                custom_experiment_name=f"{self.custom_image_prefix}",
                datetime_str=datetime.now().strftime(DATETIME_FORMAT),
                experiment_initialization_metadata={},
                per_image_metadata_keys=self.getMetadata().keys(),
            )

            self.im_counter = 0
            self.start_time = perf_counter()

    def changeBinningMode(self):
        if self.camera_activated:
            self.camera.stopAcquisition()
            self.camera_activated = False

        if self.camera.getBinning() == 2:
            print("Changing to 1x1 binning.")
            self.binning = 1
            self.camera.setBinning(bin_factor=1, mode="Average")
        else:
            print("Changing to 2x2 binning.")
            self.binning = 2
            self.camera.setBinning(bin_factor=2, mode="Average")

        self.camera_activated = True

    def runFullZStack(self):
        self.takeZStack = True
        self.zstack = full_sweep_image_collection(
            motor=self.motor, steps_per_coarse=10, save_loc=self.external_dir
        )
        self.zstack.send(None)

    def runLocalZStack(self):
        self.takeZStack = True
        self.mscope.fan.turn_off_all()
        self.zstack = local_sweep_image_collection(
            self.motor, self.motor.pos, save_loc=self.external_dir
        )
        self.zstack.send(None)

    def zStack(self, image):
        if self.takeZStack:
            try:
                self.zstack.send(image)
                self.motorPosChanged.emit(self.motor.pos)
            except StopIteration:
                self.takeZStack = False
                self.motorPosChanged.emit(self.motor.pos)
                self.zStackFinished.emit(1)
                self.mscope.fan.turn_on_all()
            except ValueError:
                # Occurs if an image is sent while the function is still moving the motor
                pass

    def _autobrightness(self, img: np.ndarray):
        if self.autobrightness_on:
            try:
                self.autobrightness.send(img)
            except StopIteration as e:
                final_brightness = e.value
                print(f"Mean pixel val: {final_brightness}")
                self.autobrightness_on = False
                self.autobrightnessDone.emit(1)
            except BrightnessTargetNotAchieved as e:
                print(f"Autobrightness error - {e.__class__.__name__}.")
                self.autobrightness_on = False
                self.autobrightnessDone.emit(1)
                return
            except BrightnessCriticallyLow as e:
                print(f"Autobrightness error - {e.__class__.__name__}")
                self.autobrightness_on = False
                self.autobrightnessDone.emit(1)
                return
            except LEDNoPower as e:
                print(f"Autobrightness error - {e.__class__.__name__}")

    def _set_target_flowrate(self, val):
        self.target_flowrate = val

    def initializeActiveFlowControl(self):
        self.fastFlowRoutine = self.routines.flow_control_routine(
            self.mscope, self.target_flowrate, fast_flow=True
        )
        self.initializeFlowControl = False
        self.fast_flow_enabled = True

    def stopActiveFlowControl(self):
        self.fast_flow_enabled = False
        self.flowcontrol_enabled = False
        self.initializeFlowControl = False

    def activeFlowControl(self, img: np.ndarray):
        if self.initializeFlowControl:
            self.initializeActiveFlowControl()

        if self.fast_flow_enabled:
            try:
                flow_val = self.fastFlowRoutine.send((img, self.timestamp))
                if flow_val is not None:
                    self.flowValChanged.emit(flow_val)
            except StopIteration as e:
                final_val = e.value
                self.flowControl = self.routines.flow_control_routine(
                    self.mscope, self.target_flowrate, fast_flow=False
                )
                self.fast_flow_enabled = False
                self.flowcontrol_enabled = True
                print(f"Final fast flow val: {final_val}")
            except CantReachTargetFlowrate:
                self.stopActiveFlowControl()
                print(
                    f"Unable to reach target flowrate: {self.target_flowrate}. Disabling active flow control."
                )
                self.pressureLeakDetected.emit(1)
            except LowConfidenceCorrelations:
                self.stopActiveFlowControl()
                print(
                    "A number of recent xcorr calculations have failed. Disabling active flow control."
                )
                self.pressureLeakDetected.emit(1)

        if self.flowcontrol_enabled:
            try:
                flow_val = self.flowControl.send((img, self.timestamp))
                self.syringePosChanged.emit(1)
                if flow_val is not None:
                    self.flowValChanged.emit(flow_val)
            except CantReachTargetFlowrate:
                self.stopActiveFlowControl()
                print(
                    f"Unable to reach the target flowrate. Current: {flow_val}, target: {self.target_flowrate}"
                )
                self.pressureLeakDetected.emit(1)

    def autofocusWrapper(self, img: np.ndarray):
        self.af_adjustment_done = False
        if perf_counter() - self.prev_autofocus_time > nn_constants.AF_PERIOD_S:
            self.autofocus(img)
            self.prev_autofocus_time = perf_counter()

    def autofocus(self, img: np.ndarray):
        """Takes in a single image and determines the number of steps
        to move the motor to the peak focus"""
        if self.active_autofocus:
            print("Autofocusing!")
            try:
                resized_img = cv2.resize(
                    img, IMG_RESIZED_DIMS, interpolation=cv2.INTER_CUBIC
                )
                steps_from_focus = -int(self.autofocus_model(resized_img).pop())
                print(f"SSAF: {steps_from_focus} steps")
                self.af_adjustment_done = True

                try:
                    dir = Direction.CW if steps_from_focus > 0 else Direction.CCW
                    self.motor.threaded_move_rel(dir=dir, steps=abs(steps_from_focus))
                except MotorControllerError:
                    print(
                        "Error moving motor after receiving steps from the SSAF model."
                    )

            except Exception as e:
                print(f"Generic model inference error: {e}")


class MalariaScopeGUI(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        media_dir = SSD_DIR

        if SIMULATION:
            print("---------------------\n|  SIMULATION MODE  |\n---------------------")

            if not VIDEO_PATH.exists():
                print(
                    "Error - no sample video exists. To add your own video, save it under "
                    + str(VIDEO_PATH)
                    + "\nRecommended video: "
                    + VIDEO_REC
                )
                quit()

        try:
            self.external_dir = media_dir + listdir(media_dir)[0] + "/"
        except IndexError:
            retval = self._displayMessageBox(
                QtWidgets.QMessageBox.Icon.Critical,
                "Error - harddrive not detected.",
                "ERROR! No external harddrive / SSD detected. Press OK to close the application.",
                cancel=False,
            )
            if retval == QtWidgets.QMessageBox.Ok:
                quit()

        # List hardware components
        self.acquisitionThread = None
        self.motor = None
        self.pneumatic_module = None
        self.encoder = None
        self.led = None

        # Create scope object
        mscope = MalariaScope()
        self.mscope = mscope
        self.mscope.set_gpio_callback(self.lid_open_handler)

        hardware_status = mscope.getComponentStatus()
        self.fan = mscope.fan

        # Load the ui file
        uic.loadUi(_UI_FILE_DIR, self)

        # Start the video stream
        self.acquisitionThread = AcquisitionThread(self.external_dir, mscope)
        self.recording = False
        if not hardware_status[Components.CAMERA]:
            print("Error initializing camera. Disabling camera GUI elements.")
            self.btnSnap.setEnabled(False)
            self.chkBoxRecord.setEnabled(False)
            self.txtBoxExposure.setEnabled(False)
            self.vsExposure.setEnabled(False)

        # Create the LED
        try:
            self.led = mscope.led
            self.led.turnOn()
            self.led.setDutyCycle(0)
            self.vsLED.setValue(0)
            self.lblLED.setText(f"{int(self.vsLED.value())}%")
            self.btnLEDToggle.setText("Turn off")
            self.vsLED.valueChanged.connect(self.vsLEDHandler)
            self.btnLEDToggle.clicked.connect(self.btnLEDToggleHandler)
            self.btnAutobrightness.clicked.connect(self.btnAutobrightnessHandler)

        except LEDError:
            print("Error instantiating LED. Continuing...")

        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = mscope.motor
            print("Moving motor to the middle.")
            sleep(0.5)
            self.motor.move_abs(int(self.motor.max_pos // 2))
            self.lblFocusMax.setText(f"{self.motor.max_pos}")

            self.btnFullZStack.setText("Full sweep+save")
            self.btnLocalZStack.setText("Local sweep+save")

            self.btnFocusUp.clicked.connect(self.btnFocusUpHandler)
            self.btnFocusDown.clicked.connect(self.btnFocusDownHandler)
            self.chkBoxFreeze.stateChanged.connect(self.chkBoxFreezeHandler)
            self.btnNextImage.clicked.connect(self.btnNextImageHandler)
            self.vsFocus.valueChanged.connect(self.vsFocusValueChangedHandler)
            self.vsFocus.sliderReleased.connect(self.vsFocusSliderReleasedHandler)
            self.vsFocus.sliderPressed.connect(self.vsFocusClickHandler)
            self.txtBoxFocus.editingFinished.connect(self.focusTextBoxHandler)
            self.txtBoxFocus.gotFocus.connect(self.txtBoxFocusGotFocus)
            self.btnFullZStack.clicked.connect(self.btnFullZStackHandler)
            self.btnLocalZStack.clicked.connect(self.btnLocalZStackHandler)
            self.chkBoxActiveAutofocus.stateChanged.connect(
                self.chkBoxActiveAutofocusHandler
            )
            self.vsFocus.setMinimum(0)
            self.vsFocus.setValue(self.motor.pos)
            self.vsFocus.setMaximum(self.motor.max_pos)

        except MotorControllerError as e:
            print(
                f"Error initializing DRV8825. Disabling focus actuation GUI elements.\nSpecific error: {e}"
            )
            self.btnFocusUp.setEnabled(False)
            self.btnFocusDown.setEnabled(False)
            self.vsFocus.setEnabled(False)
            self.txtBoxFocus.setEnabled(False)

        # Create pressure controller (sensor + servo)
        try:
            self.pneumatic_module = mscope.pneumatic_module
            num_steps = int(
                (
                    self.pneumatic_module.getMaxDutyCycle()
                    - self.pneumatic_module.getMinDutyCycle()
                )
                / self.pneumatic_module.min_step_size
            )
            self.vsFlow.setMinimum(0)
            self.vsFlow.setMaximum(num_steps)
            self.vsFlow.setSingleStep(1)
            self.txtBoxFlow.setText(f"{self.pneumatic_module.getCurrentDutyCycle()}")
            self.vsFlow.setValue(
                self.convertTovsFlowVal(self.pneumatic_module.getCurrentDutyCycle())
            )
        except PneumaticModuleError as e:
            print(
                f"Error initializing Pressure Controller. Disabling flow GUI elements. Error: {e}"
            )
            self.btnFlowUp.setEnabled(False)
            self.btnFlowDown.setEnabled(False)
            self.vsFlow.setEnabled(False)
            self.txtBoxFlow.setEnabled(False)

        # Connect the encoder
        try:
            self.encoder = mscope.encoder
        except EncoderI2CError as e:
            print(f"ENCODER I2C ERROR: {e}")
        except Exception as e:
            print(f"Encoder uncaught error: {e}")

        ### Connect UI elements to actions ###

        # Acquisition thread
        self.acquisitionThread.changePixmap.connect(self.updateImage)
        self.acquisitionThread.motorPosChanged.connect(self.updateMotorPosition)
        self.acquisitionThread.zStackFinished.connect(self.enableMotorUIElements)
        self.acquisitionThread.updatePressure.connect(self.updatePressureLabel)
        self.acquisitionThread.fps.connect(self.updateFPS)
        self.acquisitionThread.temperatures.connect(self.updateTemperatures)
        self.acquisitionThread.measurementTime.connect(self.updateMeasurementTimer)
        self.acquisitionThread.pressureLeakDetected.connect(self.pressureLeak)
        self.acquisitionThread.syringePosChanged.connect(self.updateSyringePos)
        self.acquisitionThread.flowValChanged.connect(self.updateFlowVal)
        self.acquisitionThread.autobrightnessDone.connect(self.autobrightnessDone)
        self.acquisitionThread.doneSaving.connect(self.enableRecording)
        self.acquisitionThread._set_target_flowrate(FLOWRATE.MEDIUM.value)

        self.acquisitionThread.start()

        # GUI element signals
        self.txtBoxExposure.editingFinished.connect(self.exposureTextBoxHandler)
        self.chkBoxRecord.stateChanged.connect(self.checkBoxRecordHandler)
        self.chkBoxMaxFPS.stateChanged.connect(self.checkBoxMaxFPSHandler)
        self.btnSnap.clicked.connect(self.btnSnapHandler)
        self.vsExposure.valueChanged.connect(self.exposureSliderHandler)
        self.btnChangeBinning.clicked.connect(self.btnChangeBinningHandler)
        self.btnQCForm.clicked.connect(self.btnQCFormHandler)

        # Pressure control
        self.btnFlowUp.clicked.connect(self.btnFlowUpHandler)
        self.btnFlowDown.clicked.connect(self.btnFlowDownHandler)
        self.txtBoxFlow.editingFinished.connect(self.flowTextBoxHandler)
        self.txtBoxFlow.gotFocus.connect(self.txtBoxFlowGotFocus)
        self.vsFlow.valueChanged.connect(self.vsFlowValueChangedHandler)
        self.vsFlow.sliderReleased.connect(self.vsFlowSliderReleasedHandler)
        self.vsFlow.sliderPressed.connect(self.vsFlowClickHandler)
        self.chkBoxFlowControl.stateChanged.connect(self.activeFlowControlHandler)
        self.radFlowSlow.toggled.connect(self.setFlowrate)
        self.radFlowMed.toggled.connect(self.setFlowrate)
        self.radFlowFast.toggled.connect(self.setFlowrate)

        # Misc
        self.fan.turn_on_all()
        self.btnExit.clicked.connect(self.exit)
        try:
            ngrok_address = make_tcp_tunnel()
            send_ngrok_email()
        except NgrokError as e:
            print(f"Ngrok error : {e}")
            ngrok_address = "-ngrok error-"
        self.lblngrok.setText(f"{ngrok_address}")

        # Set slider min/max
        self.min_exposure_us = 100
        self.max_exposure_us = 10000
        self.vsExposure.setMinimum(self.min_exposure_us)
        self.vsExposure.setMaximum(self.max_exposure_us)
        self.vsExposure.setValue(500)
        self.lblMinExposure.setText(f"{self.min_exposure_us} us")
        self.lblMaxExposure.setText(f"{self.max_exposure_us} us")

    def _displayMessageBox(self, icon, title, text, cancel):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(icon)
        msgBox.setWindowTitle(f"{title}")
        msgBox.setText(f"{text}")
        if cancel:
            msgBox.setStandardButtons(
                QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel
            )
        else:
            msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok)
        return msgBox.exec()

    def txtBoxFocusGotFocus(self):
        self.acquisitionThread.updateMotorPos = False

    def txtBoxFlowGotFocus(self):
        self.acquisitionThread.updateSyringePos = False

    def vsFocusClickHandler(self):
        self.acquisitionThread.updateMotorPos = False

    def vsFlowClickHandler(self):
        self.acquisitionThread.updateSyringePos = False

    def checkBoxRecordHandler(self):
        if self.chkBoxRecord.checkState():
            # Continuously record images to a new subfolder
            self.btnSnap.setText("Record images")
        else:
            self.btnSnap.setText("Take image")

    def checkBoxMaxFPSHandler(self):
        if self.chkBoxMaxFPS.checkState():
            self.acquisitionThread.update_liveview = 45
        else:
            self.acquisitionThread.update_liveview = 1

    def btnSnapHandler(self):
        if self.recording:
            self.recording = False
            self.acquisitionThread.continuous_save = False
            self.btnSnap.setText("Closing file...")
            self.btnSnap.setEnabled(False)
            sleep(0.1)
            self.acquisitionThread.finish_saving_future = (
                self.acquisitionThread.data_storage.close()
            )
            end_time = perf_counter()
            start_time = self.acquisitionThread.start_time
            num_images = self.acquisitionThread.im_counter
            print(
                f"{num_images} images taken in {end_time - start_time:.2f}s ({num_images / (end_time-start_time):.2f} fps)"
            )

            retval = self._displayMessageBox(
                QtWidgets.QMessageBox.Icon.Information,
                "Open Flowcell QC Post-run Form?",
                "Press okay to open the Google form. A browser window will be opened.",
                cancel=True,
            )
            if retval == QtWidgets.QMessageBox.Ok:
                webbrowser.open(FLOWCELL_QC_FORM_LINK, new=1, autoraise=True)

            return

        # Set custom name
        custom_filename = "_" + self.txtBoxCustomFilename.text().replace(" ", "")
        self.acquisitionThread.custom_image_prefix = (
            custom_filename if custom_filename != "_" else ""
        )

        if self.chkBoxRecord.checkState():
            self.acquisitionThread.continuous_save = True
            self.btnSnap.setText("Stop recording")
            self.recording = True
            self.chkBoxRecord.setEnabled(False)
            self.chkBoxMaxFPS.setEnabled(False)
            self.acquisitionThread.takeImage()
        else:
            self.acquisitionThread.single_save = True
            self.acquisitionThread.takeImage()

    def btnChangeBinningHandler(self):
        self.acquisitionThread.changeBinningMode()
        curr_binning_mode = self.acquisitionThread.camera.getBinning()
        change_to = 1 if curr_binning_mode == 2 else 2
        self.btnChangeBinning.setText(f"Change to {change_to}X binning")

    def btnQCFormHandler(self):
        retval = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Information,
            "Open Flowcell QC Post-run Form?",
            "Press okay to open the Google form. A browser window will be opened.",
            cancel=True,
        )
        if retval == QtWidgets.QMessageBox.Ok:
            webbrowser.open(FLOWCELL_QC_FORM_LINK, new=1, autoraise=True)

    @pyqtSlot(QImage)
    def updateImage(self, qimage):
        self.lblImage.setPixmap(QPixmap.fromImage(qimage))

    @pyqtSlot(int)
    def updateMotorPosition(self, val):
        self.vsFocus.setValue(val)
        self.txtBoxFocus.setText(f"{val}")

    @pyqtSlot(int)
    def updateSyringePos(self, _):
        self.vsFlow.setValue(
            self.convertTovsFlowVal(self.pneumatic_module.getCurrentDutyCycle())
        )
        duty_cycle = self.pneumatic_module.duty_cycle
        self.txtBoxFlow.setText(f"{duty_cycle}")

    @pyqtSlot(float)
    def updateFlowVal(self, flow_val):
        if flow_val is not None:
            self.lblFlowrate.setText(f"Flowrate: {flow_val:.2f}")

    @pyqtSlot(float)
    def updatePressureLabel(self, val):
        self.lblPressure.setText(f"{val:.2f} hPa")

    @pyqtSlot(int)
    def updateFPS(self, val):
        self.lblFPS.setText(f"{val}fps")

    @pyqtSlot(int)
    def updateTemperatures(self, _):
        cam_temp = -1
        try:
            cam_temp = self.acquisitionThread.mscope.camera._getTemperature()
        except Exception as e:
            print(f"Unable to get camera temperature: {e}")

        sens_temp = -1
        try:
            (
                sens_temp,
                _,
            ) = self.acquisitionThread.mscope.ht_sensor.get_temp_and_humidity()
        except Exception as e:
            print(f"Unable to get ambient temperature sensor value: {e}")

        self.lblTemperatures.setText(
            f"C: {cam_temp:.2f} CPU: {cpu.temperature:.2f} A: {sens_temp:.2f} (C)"
        )

    @pyqtSlot(int)
    def updateMeasurementTimer(self, val):
        self.lblTimer.setText(f"{str(timedelta(seconds=val))}")

    @pyqtSlot(int)
    def enableRecording(self, _):
        self.btnSnap.setText("Record images")
        self.btnSnap.setEnabled(True)
        self.chkBoxRecord.setEnabled(True)
        self.chkBoxMaxFPS.setEnabled(True)

    def _enableLEDGUIElements(self):
        self.vsLED.blockSignals(False)
        self.vsLED.setEnabled(True)
        self.led.setDutyCycle(int(self.vsLED.value()) / 100)
        self.btnLEDToggle.setText("Turn off")

    def _disableLEDGUIElements(self):
        self.vsLED.blockSignals(True)
        self.vsLED.setEnabled(False)
        self.btnLEDToggle.setText("Turn on")

    def btnLEDToggleHandler(self):
        if self.led._isOn:
            self.led.turnOff()
            self._disableLEDGUIElements()
        else:
            self.led.turnOn()
            self._enableLEDGUIElements()

    def btnAutobrightnessHandler(self):
        self.acquisitionThread.autobrightness = (
            self.acquisitionThread.routines.autobrightnessRoutine(self.mscope)
        )
        self.btnAutobrightness.setEnabled(False)
        self.btnLEDToggle.setEnabled(False)
        self.vsLED.blockSignals(True)
        self.vsLED.setEnabled(False)
        self.acquisitionThread.autobrightness_on = True
        self.btnLEDToggle.setText("Turn off")

    @pyqtSlot(int)
    def autobrightnessDone(self, val):
        self.btnAutobrightness.setEnabled(True)
        self.btnLEDToggle.setEnabled(True)
        self.vsLED.blockSignals(False)
        self.vsLED.setEnabled(True)
        new_val = self.led.pwm_duty_cycle * 100
        self.vsLED.setValue(new_val)
        self.lblLED.setText(f"{int(new_val)}%")

    def vsLEDHandler(self):
        perc = int(self.vsLED.value())
        self.lblLED.setText(f"{int(perc)}%")
        self.led.setDutyCycle(perc / 100)

    def lid_open_handler(self, *args):
        if self.mscope.led._isOn:
            self.mscope.led.turnOff()
            self._disableLEDGUIElements()

    def lid_closed_handler(self, *args):
        if not self.mscope.led._isOn:
            self.mscope.led.turnOn()
            self._enableLEDGUIElements()

    def exposureSliderHandler(self):
        exposure = int(self.vsExposure.value())
        self.acquisitionThread.updateExposure(exposure / 1000)  # Exposure time us -> ms
        self.txtBoxExposure.setText(f"{exposure}")

    def exposureTextBoxHandler(self):
        try:
            exposure = int(float(self.txtBoxExposure.text()))
            if exposure < self.min_exposure_us or exposure > self.max_exposure_us:
                raise
        except:
            print("Error parsing textbox exposure time input. Continuing...")
            self.txtBoxExposure.setText(f"{self.vsExposure.value()}")
            return
        try:
            self.acquisitionThread.updateExposure(
                exposure / 1000
            )  # Exposure time us -> ms
        except:
            print("Invalid exposure, ignoring and continuing...")
            self.txtBoxExposure.setText(f"{self.vsExposure.value()}")
            return
        self.vsExposure.setValue(exposure)

    def btnFocusUpHandler(self):
        try:
            self.motor.threaded_move_rel(dir=Direction.CW, steps=1)
        except MotorInMotion as e:
            print(e)

        self.vsFocus.setValue(self.motor.pos)
        self.txtBoxFocus.setText(f"{self.motor.pos}")

    def btnFocusDownHandler(self):
        try:
            self.motor.threaded_move_rel(dir=Direction.CCW, steps=1)
        except MotorInMotion as e:
            print(e)

        self.vsFocus.setValue(self.motor.pos)
        self.txtBoxFocus.setText(f"{self.motor.pos}")

    def chkBoxFreezeHandler(self):
        if self.chkBoxFreeze.checkState():
            self.acquisitionThread.liveview = False
            self.btnNextImage.setEnabled(True)
        else:
            self.acquisitionThread.liveview = True
            self.btnNextImage.setEnabled(False)

    def btnNextImageHandler(self):
        self.acquisitionThread.click_to_advance = True

    def vsFocusValueChangedHandler(self):
        pos = int(self.vsFocus.value())
        self.txtBoxFocus.setText(f"{pos}")

    def vsFocusSliderReleasedHandler(self):
        pos = int(self.vsFocus.value())
        try:
            self.motor.threaded_move_abs(pos)
        except MotorInMotion:
            print("Motor already in motion.")

        self.txtBoxFocus.setText(f"{self.motor.pos}")
        self.acquisitionThread.updateMotorPos = True

    def focusTextBoxHandler(self):
        try:
            pos = int(float(self.txtBoxFocus.text()))
        except:
            print("Error parsing textbox focus position. Continuing...")
            self.txtBoxFocus.setText(f"{self.vsFocus.value()}")
            return

        try:
            self.motor.threaded_move_abs(pos)
        except MotorInMotion:
            print("Motor already in motion.")
            self.txtBoxFocus.setText(f"{self.vsFocus.value()}")
            return

        self.vsFocus.setValue(pos)
        self.acquisitionThread.updateMotorPos = True

    def btnFullZStackHandler(self):
        retval = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Information,
            "Full Range ZStack",
            "Press okay to sweep the motor over its entire range and save the images (save 1 img/step).",
            cancel=True,
        )

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runFullZStack()

    def btnLocalZStackHandler(self):
        retval = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Information,
            "Local Vicinity ZStack",
            "Press okay to sweep the motor over its current nearby vicinity and save images (note: by default we save 30 imgs/step so this may be slow).\nNOTE: the fans will turn off temporarily!\nDo not be alarmed!!!\nStay CALM!!!!",
            cancel=True,
        )

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runLocalZStack()

    def chkBoxActiveAutofocusHandler(self):
        if self.chkBoxActiveAutofocus.checkState():
            print("Autofocus enabled")
            self.disableMotorUIElements()
            self.acquisitionThread.active_autofocus = True

        else:
            self.acquisitionThread.active_autofocus = False
            self.enableMotorUIElements()

    def disableMotorUIElements(self):
        self.vsFocus.blockSignals(True)
        self.txtBoxFocus.blockSignals(True)
        self.btnFocusUp.setEnabled(False)
        self.btnFocusDown.setEnabled(False)
        self.btnLocalZStack.setEnabled(False)
        self.btnFullZStack.setEnabled(False)

    @pyqtSlot(int)
    def enableMotorUIElements(self, val=None):
        self.btnFocusUp.setEnabled(True)
        self.btnFocusDown.setEnabled(True)
        self.btnLocalZStack.setEnabled(True)
        self.btnFullZStack.setEnabled(True)
        self.vsFocus.blockSignals(False)
        self.txtBoxFocus.blockSignals(False)

    def btnFlowUpHandler(self):
        try:
            self.pneumatic_module.threadedIncreaseDutyCycle()
            duty_cycle = self.pneumatic_module.duty_cycle
            self.vsFlow.setValue(self.convertTovsFlowVal(duty_cycle))
            self.txtBoxFlow.setText(f"{duty_cycle}")
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        except SyringeEndOfTravel:
            print("Syringe end of travel (top range).")

    def btnFlowDownHandler(self):
        try:
            self.pneumatic_module.threadedDecreaseDutyCycle()
            duty_cycle = self.pneumatic_module.duty_cycle
            self.vsFlow.setValue(self.convertTovsFlowVal(duty_cycle))
            self.txtBoxFlow.setText(f"{duty_cycle}")
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        except SyringeEndOfTravel:
            print("Syringe end of travel (bottom range).")

    def convertFromvsFlowVal(self):
        return (
            self.vsFlow.value() * self.pneumatic_module.min_step_size
            + self.pneumatic_module.getMinDutyCycle()
        )

    def convertTovsFlowVal(self, val):
        return int(
            (val - self.pneumatic_module.getMinDutyCycle())
            / self.pneumatic_module.min_step_size
        )

    def vsFlowValueChangedHandler(self):
        val = self.convertFromvsFlowVal()
        self.txtBoxFlow.setText(f"{val}")

    def vsFlowSliderReleasedHandler(self):
        flow_duty_cycle = self.convertFromvsFlowVal()
        try:
            self.pneumatic_module.threadedSetDutyCycle(flow_duty_cycle)
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        self.txtBoxFlow.setText(f"{flow_duty_cycle}")
        self.acquisitionThread.updateSyringePos = True

    def flowTextBoxHandler(self):
        try:
            flow_duty_cycle = int(float(self.txtBoxFlow.text()))
        except:
            print("Error parsing textbox flow PWM input. Continuing...")
            self.txtBoxFlow.setText(f"{self.convertFromvsFlowVal(self.vsFlow.value())}")
            return

        try:
            self.pneumatic_module.threadedSetDutyCycle(flow_duty_cycle)
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        except:
            print("Invalid duty cycle, ignoring and continuing...")
            self.txtBoxFlow.setText(f"{self.convertFromvsFlowVal(self.vsFlow.value())}")
            return

        self.vsFlow.setValue(self.convertTovsFlowVal(flow_duty_cycle))
        self.acquisitionThread.updateSyringePos = True

    def activeFlowControlHandler(self):
        if self.chkBoxFlowControl.checkState():
            self.acquisitionThread.flowcontrol_enabled = False
            self.acquisitionThread.fast_flow_enabled = False
            self.acquisitionThread.initializeFlowControl = True
            self.disablePressureUIElements()
        else:
            self.acquisitionThread.stopActiveFlowControl()
            self.enablePressureUIElements()

    def setFlowrate(self):
        if self.radFlowSlow.isChecked():
            self.acquisitionThread._set_target_flowrate(FLOWRATE.SLOW.value)
            print(f"Slow flow target: {FLOWRATE.SLOW.value}")
        elif self.radFlowMed.isChecked():
            self.acquisitionThread._set_target_flowrate(FLOWRATE.MEDIUM.value)
            print(f"Med flow target: {FLOWRATE.MEDIUM.value}")
        elif self.radFlowFast.isChecked():
            self.acquisitionThread._set_target_flowrate(FLOWRATE.FAST.value)
            print(f"Fast flow target: {FLOWRATE.FAST.value}")

    def enablePressureUIElements(self):
        self.vsFlow.blockSignals(False)
        self.vsFlow.setEnabled(True)
        self.txtBoxFlow.blockSignals(False)
        self.btnFlowUp.setEnabled(True)
        self.btnFlowDown.setEnabled(True)
        self.radFlowSlow.setEnabled(True)
        self.radFlowMed.setEnabled(True)
        self.radFlowFast.setEnabled(True)

    def disablePressureUIElements(self):
        self.vsFlow.blockSignals(True)
        self.vsFlow.setEnabled(False)
        self.txtBoxFlow.blockSignals(True)
        self.btnFlowUp.setEnabled(False)
        self.btnFlowDown.setEnabled(False)
        self.radFlowSlow.setEnabled(False)
        self.radFlowMed.setEnabled(False)
        self.radFlowFast.setEnabled(False)

    @pyqtSlot(int)
    def pressureLeak(self, _):
        self.chkBoxFlowControl.setChecked(False)
        self.enablePressureUIElements()
        _ = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Warning,
            "Leak - Active pressure controlled stopped",
            "The target flowrate can not be attained, stopping active flow control.",
            cancel=False,
        )

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

    def exit(self):
        retval = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Warning,
            "Exit application",
            "Please remove the flow cell now. Only press okay after the flow cell has been removed. The syringe will move into the topmost position after pressing okay.",
            cancel=True,
        )

        if retval == QtWidgets.QMessageBox.Ok:
            # Move syringe back and de-energize
            self.pneumatic_module.close()

            # Turn off the LED
            self.led.close()

            # Turn off camera
            if self.acquisitionThread is not None:
                self.acquisitionThread.camera_activated = False
                self.acquisitionThread.camera.stopAcquisition()
                self.acquisitionThread.camera.deactivateCamera()

            # Turn off encoder
            if self.encoder:
                self.encoder.close()

            try:
                os.remove(LOCKFILE)
                print(f"Removed lockfile ({LOCKFILE}).")
            except FileNotFoundError:
                print(f"Lockfile ({LOCKFILE}) does not exist and could not be deleted.")

            quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()


if __name__ == "__main__":
    if path.isfile(LOCKFILE):
        print(
            f"Terminating run. Lockfile ({LOCKFILE}) exists, so scope is locked while another run is in progress."
        )
        text = input("Enter 'y' to continue anyway, or enter to exit: ")
        if text != "y":
            sys.exit(1)
        else:
            open(LOCKFILE, "w")
    else:
        open(LOCKFILE, "w")

    try:
        app = QtWidgets.QApplication(sys.argv)
        main_window = MalariaScopeGUI()
        main_window.show()
        app.exec_()
    finally:
        main_window.mscope.shutoff()
