from gui_constants import *

from ulc_mm_package.hardware.hardware_constants import VIDEO_PATH, VIDEO_REC
from ulc_mm_package.hardware.hardware_modules import *

from ulc_mm_package.image_processing.processing_modules import *

from ulc_mm_package.utilities.generate_msfc_ids import is_luhn_valid

from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus
import ulc_mm_package.neural_nets.ssaf_constants as ssaf_constants

import sys
import csv
import traceback
import numpy as np
import webbrowser

from typing import Dict
from time import perf_counter, sleep
from os import listdir, mkdir, path
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from cv2 import imwrite
from qimage2ndarray import gray2qimage

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# Qt GUI Files
_UI_FILE_DIR = "liveview.ui"
_EXPERIMENT_FORM_PATH = "experimentform.ui"

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
    pressureLeakDetected = pyqtSignal(int)
    syringePosChanged = pyqtSignal(int)
    autobrightnessDone = pyqtSignal(int)

    def __init__(self, external_dir):
        super().__init__()
        self._initializeAttributes(external_dir)

        try:
            if CAMERA_SELECTION == 0:
                self.camera = BaslerCamera()
            elif CAMERA_SELECTION == 1:
                self.camera = AVTCamera()
            else:
                raise ApplicationError(f"Invalid camera selection: must be 0 (Basler) or 1 (AVT). It is currently {CAMERA_SELECTION}.")
            self.camera_activated = True
        except CameraError:
            self.camera_activated = False

    def _initializeAttributes(self, external_dir: str):
        """Initialize attributes (variables, flags, references to hardware peripherals)
        in this function to make the __init__ more readable."""

        # Flags and counters
        self.update_liveview = 1
        self.im_counter = 0
        self.update_counter = 0
        self.num_loops = 50
        self.camera_activated = False
        self.main_dir = None
        self.single_save = False
        self.continuous_save = False
        self.liveview = True
        self.takeZStack = False
        self.continuous_dir_name = None
        self.custom_image_prefix = ""
        self.updateMotorPos = True
        self.updateSyringePos = True
        self.fps_timer = perf_counter()
        self.start_time = perf_counter()
        self.external_dir = external_dir
        self.metadata_writer = None
        self.click_to_advance = False
        self.md_writer = None
        self.metadata_file = None

        # Hardware peripherals
        self.motor = None
        self.pneumatic_module: PneumaticModule = None
        self.zw = ZarrWriter()

        self.flow_controller: FlowController = FlowController(self.pneumatic_module, 600, 800) # default shell
        self.initializeFlowControl = False
        self.flowcontrol_enabled = False
        self.autobrightness: Autobrightness = None
        self.autobrightness_on = False

        # Single-shot autofocus
        try:
            self.autofocus_model = AutoFocus(AUTOFOCUS_MODEL_DIR)
        except RuntimeError as e:
            raise RuntimeError(f'got {str(e)}:\n {subprocess.getoutput("lsusb | grep Myriad")=}')
        self.active_autofocus = False
        self.prev_autofocus_time = 0
        self.af_adjustment_done = False

    def run(self):
        while True:
            if self.camera_activated:
                try:
                    for image in self.camera.yieldImages():
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

        return {
            "im_counter": self.im_counter,
            "measurement_type": "placeholder",
            "sample_type": "placeholder",
            "timestamp": datetime.now().strftime("%Y-%m-%d-%H%M%S_%f"),
            "exposure": self.camera.exposureTime_ms,
            "motor_pos": self.motor.pos,
            "pressure_hpa": self.pneumatic_module.getPressure(),
            "syringe_pos": self.pneumatic_module.getCurrentDutyCycle(),
            "flow_control_on": self.flowcontrol_enabled,
            "target_flowrate": self.flow_controller.target_flowrate,
            "current_flowrate": self.flow_controller.curr_flowrate,
            "focus_adjustment": self.af_adjustment_done,
        }

    def save(self, image):
        if self.single_save:
            filename = (
                path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S"))
                + f"{self.custom_image_prefix}.png"
            )
            imwrite(filename, image)
            self.single_save = False

        if self.continuous_save and self.continuous_dir_name != None:
            if self.zw.writable:
                self.zw.writeSingleArray(image)
                self.md_writer.writerow(self.getMetadata())
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
            if self.pneumatic_module != None:
                try:
                    pressure = self.pneumatic_module.getPressure()
                    self.updatePressure.emit(pressure)
                except Exception:
                    print("Error getting pressure. Continuing...")
            self.fps.emit(int(self.num_loops / (perf_counter() - self.fps_timer)))
            self.fps_timer = perf_counter()

    def updateExposure(self, exposure):
        self.camera.exposureTime_ms = exposure

    def takeImage(self):
        if self.main_dir == None:
            self.main_dir = self.external_dir + datetime.now().strftime(
                "%Y-%m-%d-%H%M%S"
            )
            mkdir(self.main_dir)

        if self.continuous_save:
            self.continuous_dir_name = (
                datetime.now().strftime("%Y-%m-%d-%H%M%S")
                + f"{self.custom_image_prefix}"
            )
            mkdir(path.join(self.main_dir, self.continuous_dir_name))

            filename = (
                path.join(
                    self.main_dir,
                    self.continuous_dir_name,
                    datetime.now().strftime("%Y-%m-%d-%H%M%S"),
                )
                + f"{self.custom_image_prefix}"
            )
            if self.md_writer:
                self.metadata_file.close()
            self.metadata_file = open(f"{filename}_metadata.csv", "w")
            self.md_writer = csv.DictWriter(self.metadata_file, fieldnames=self.getMetadata().keys())
            self.md_writer.writeheader()

            self.zw.createNewFile(filename)

            self.start_time = perf_counter()

            self.im_counter = 0
            self.timings = []

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

    def runFullZStack(self, motor: DRV8825Nema):
        self.takeZStack = True
        self.motor = motor
        self.zstack = takeZStackCoroutine(None, motor, save_loc=self.external_dir)
        self.zstack.send(None)

    def runLocalZStack(self, motor: DRV8825Nema, start_point: int):
        self.takeZStack = True
        self.motor = motor
        self.zstack = symmetricZStackCoroutine(
            None, motor, start_point, save_loc=self.external_dir
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
            except ValueError:
                # Occurs if an image is sent while the function is still moving the motor
                pass

    def _autobrightness(self, img: np.ndarray):
        if self.autobrightness_on:
            try:
                done = self.autobrightness.runAutobrightness(img)
            except AutobrightnessError as e:
                print(f"AutobrightnessError encountered: {e}. Stopping autobrightness and continuing...")
                self.autobrightness_on = False
                self.autobrightnessDone.emit(1)
                return
                
            if done:
                self.autobrightness_on = False
                self.autobrightnessDone.emit(1)

    def initializeActiveFlowControl(self, img: np.ndarray):
        h, w = img.shape
        self.flow_controller = FlowController(self.pneumatic_module, h, w)
        self.flowcontrol_enabled = True
        self.initializeFlowControl = False

    def stopActiveFlowControl(self):
        self.flowcontrol_enabled = False

    def activeFlowControl(self, img: np.ndarray):
        if self.initializeFlowControl:
            self.initializeActiveFlowControl(img)

        if self.flowcontrol_enabled:
            try:
                self.flow_controller.controlFlow(img)
                self.syringePosChanged.emit(1)
            except PressureLeak:
                print(
                    f"""The syringe is already at its maximum position but the current flow rate is either above or below the target.\n
                        Active flow control is now disabled.
                        """
                )
                self.pressureLeakDetected.emit(1)

    def autofocusWrapper(self, img: np.ndarray):
        self.af_adjustment_done = False
        if perf_counter() - self.prev_autofocus_time > ssaf_constants.AF_FREQUENCY_S:
            self.autofocus(img)
            self.prev_autofocus_time = perf_counter()

    def autofocus(self, img: np.ndarray):
        """Takes in a single image and determines the number of steps
        to move the motor to the peak focus"""
        if self.active_autofocus:
            print("Autofocusing!")
            try:
                steps_from_focus = -int(self.autofocus_model(img)[0][0][0])
                print(type(steps_from_focus), steps_from_focus)
                self.af_adjustment_done = True
            except Exception as e:
                print("Model inference error.")
            try:
                dir = Direction.CW if steps_from_focus > 0 else Direction.CCW
                self.motor.threaded_move_rel(dir=dir, steps=abs(steps_from_focus))
            except MotorControllerError:
                print("Error moving motor after receiving steps from the SSAF model.")

class ExperimentSetupGUI(QtWidgets.QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        super(ExperimentSetupGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_EXPERIMENT_FORM_PATH, self)

        # Set the focus order
        self.setTabOrder(self.txtExperimentName, self.txtFlowCellID)
        self.setTabOrder(self.txtFlowCellID, self.radBtn1x1)
        self.setTabOrder(self.radBtn1x1, self.radBtn2x2)
        self.setTabOrder(self.radBtn2x2, self.chkBoxExperimentSetupAutobrightness)
        self.setTabOrder(self.chkBoxExperimentSetupAutobrightness, self.chkBoxExperimentSetupAutofocus)
        self.setTabOrder(self.chkBoxExperimentSetupAutofocus, self.chkBoxExperimentSetupFlowControl)
        self.setTabOrder(self.chkBoxExperimentSetupFlowControl, self.sbExperimentSetupMinutes)
        
        self.txtExperimentName.setFocus()

        # Parameters
        self.experiment_name = ""
        self.flowcell_id = ""
        self.binningMode = 2
        self.autobrightness = False
        self.autofocus = False
        self.autoflowcontrol = False
        self.time_mins = None

        # Set up event handlers
        self.txtExperimentName.editingFinished.connect(self.txtExperimentNameHandler)
        self.txtFlowCellID.editingFinished.connect(self.flowCellIDHandler)
        self.radBtn1x1.toggled.connect(self.binningModeHandler)
        self.radBtn2x2.toggled.connect(self.binningModeHandler)
        self.chkBoxExperimentSetupAutobrightness.stateChanged.connect(self.chkBoxAutobrightnessHandler)
        self.chkBoxExperimentSetupAutofocus.stateChanged.connect(self.chkBoxAutofocusHandler)
        self.chkBoxExperimentSetupFlowControl.stateChanged.connect(self.chkBoxFlowControlHandler)
        self.sbExperimentSetupMinutes.valueChanged.connect(self.sbTimerHandler)
        self.btnExperimentSetupAbort.clicked.connect(self.btnAbortHandler)
        self.btnStartExperiment.clicked.connect(self.btnStartExperimentHandler)

    def txtExperimentNameHandler(self):
        self.experiment_name = self.txtExperimentName.text()
        print(self.experiment_name)
    
    def flowCellIDHandler(self):
        """TODO: Validate the flowcell ID"""
        text = self.txtFlowCellID.text()
        if is_luhn_valid(text):
            self.flowcell_id = self.txtFlowCellID.text()
        else:
            pass
        self.flowcell_id = self.txtFlowCellID.text()
        print(self.flowcell_id)
    
    def binningModeHandler(self):
        if self.radBtn1x1.isChecked():
            self.radBtn2x2.setChecked(False)
            self.binningMode = 1
        elif self.radBtn2x2.isChecked():
            self.radBtn1x1.setChecked(False)
            self.binningMode = 2
        print(f"Binning mode: {self.binningMode}")
    
    def chkBoxAutobrightnessHandler(self):
        self.autobrightness = True if self.chkBoxAutobrightness.checkState() else False
        print(self.autobrightness)

    def chkBoxAutofocusHandler(self):
        self.autofocus = True if self.chkBoxAutofocus.checkState() else False
        print(self.autofocus)
    
    def chkBoxFlowControlHandler(self):
        self.autoflowcontrol = True if self.chkBoxFlowControl.checkState() else False
        print(self.autoflowcontrol)

    def sbTimerHandler(self):
        self.time_mins = self.sbExperimentSetupMinutes.value()
        print(self.time_mins)

    def btnAbortHandler(self):
        print("Aborting experiment setup...")
        self.close()
    
    def btnStartExperimentHandler(self):
        print("Something interesting will happen here eventually...")
        parameters = self.getAllParameters()


    def getAllParameters(self) -> Dict:
        return {
            "experiment_name": self.experiment_name,
            "flowcell_id": self.flowcell_id,
            "binningMode": self.binningMode,
            "autobrightness": self.autobrightness,
            "autofocus": self.autofocus,
            "autoflowcontrol": self.autoflowcontrol,
            "time_mins": self.time_mins,
        }

class MalariaScopeGUI(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        media_dir = DEFAULT_SSD

        if SIMULATION:
            print("---------------------\n|  SIMULATION MODE  |\n---------------------")

            if not path.exists(VIDEO_PATH):
                print("Error - no sample video exists. To add your own video, save it under "
                        + VIDEO_PATH  + "\nRecommended video: " + VIDEO_REC )
                quit()

            if not path.exists(media_dir) or len(listdir(media_dir)) == 0:
                media_dir = ALT_SSD
                print("No external harddrive / SSD detected. Saving media to " + media_dir)

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
        self.fan = Fan()

        # Load the ui file
        uic.loadUi(_UI_FILE_DIR, self)

        # Experiment parameter form dialog
        self.experiment_form_dialog = ExperimentSetupGUI(self)

        # Start the video stream
        self.acquisitionThread = AcquisitionThread(self.external_dir)
        self.recording = False

        if not self.acquisitionThread.camera_activated and not SIMULATION:
            print(f"Error initializing camera. Disabling camera GUI elements.")
            self.btnSnap.setEnabled(False)
            self.chkBoxRecord.setEnabled(False)
            self.txtBoxExposure.setEnabled(False)
            self.vsExposure.setEnabled(False)

        # Create the LED
        try:
            self.led = LED_TPS5420TDDCT()
            self.led.turnOn()
            self.led.setDutyCycle(0)
            self.vsLED.setValue(0)
            self.lblLED.setText(f"{int(self.vsLED.value())}%")
            self.btnLEDToggle.setText(f"Turn off")
            self.vsLED.valueChanged.connect(self.vsLEDHandler)
            self.btnLEDToggle.clicked.connect(self.btnLEDToggleHandler)

            # Don't enable autobrightness in simulation mode
            # if not SIMULATION:
            self.btnAutobrightness.clicked.connect(self.btnAutobrightnessHandler)

        except LEDError:
            print("Error instantiating LED. Continuing...")

        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema(steptype="Half")
            self.motor.homeToLimitSwitches()
            print("Moving motor to the middle.")
            sleep(0.5)
            self.motor.move_abs(int(self.motor.max_pos // 2))
            self.lblFocusMax.setText(f"{self.motor.max_pos}")

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
            self.chkBoxActiveAutofocus.stateChanged.connect(self.chkBoxActiveAutofocusHandler)
            self.vsFocus.setMinimum(0)
            self.vsFocus.setValue(self.motor.pos)
            self.vsFocus.setMaximum(self.motor.max_pos)

        except MotorControllerError as e:
            print(f"Error initializing DRV8825. Disabling focus actuation GUI elements.\nSpecific error: {e}")
            self.btnFocusUp.setEnabled(False)
            self.btnFocusDown.setEnabled(False)
            self.vsFocus.setEnabled(False)
            self.txtBoxFocus.setEnabled(False)

        # Create pressure controller (sensor + servo)
        try:
            self.pneumatic_module = PneumaticModule()
            num_steps = int((self.pneumatic_module.getMaxDutyCycle() - self.pneumatic_module.getMinDutyCycle()) / self.pneumatic_module.min_step_size)
            self.vsFlow.setMinimum(0)
            self.vsFlow.setMaximum(num_steps)
            self.vsFlow.setSingleStep(1)
            self.txtBoxFlow.setText(f"{self.pneumatic_module.getCurrentDutyCycle()}")
            self.vsFlow.setValue(self.convertTovsFlowVal(self.pneumatic_module.getCurrentDutyCycle()))
        except PneumaticModuleError as e:
            print(f"Error initializing Pressure Controller. Disabling flow GUI elements. Error: {e}")
            self.btnFlowUp.setEnabled(False)
            self.btnFlowDown.setEnabled(False)
            self.vsFlow.setEnabled(False)
            self.txtBoxFlow.setEnabled(False)

        # Connect the encoder
        try:
            self.encoder = PIM522RotaryEncoder(self.manualFocusWithEncoder)
        except EncoderI2CError as e:
            print(f"ENCODER I2C ERROR: {e}")

        ### Connect UI elements to actions ###

        # Acquisition thread
        self.acquisitionThread.changePixmap.connect(self.updateImage)
        self.acquisitionThread.motorPosChanged.connect(self.updateMotorPosition)
        self.acquisitionThread.zStackFinished.connect(self.enableMotorUIElements)
        self.acquisitionThread.updatePressure.connect(self.updatePressureLabel)
        self.acquisitionThread.fps.connect(self.updateFPS)
        self.acquisitionThread.measurementTime.connect(self.updateMeasurementTimer)
        self.acquisitionThread.pressureLeakDetected.connect(self.pressureLeak)
        self.acquisitionThread.syringePosChanged.connect(self.updateSyringePos)
        self.acquisitionThread.autobrightnessDone.connect(self.autobrightnessDone)

        self.acquisitionThread.motor = self.motor
        self.acquisitionThread.pneumatic_module = self.pneumatic_module
        self.acquisitionThread.autobrightness = Autobrightness(self.led)
        
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

        # Misc
        self.fan.turn_on_all()
        self.btnExit.clicked.connect(self.exit)

        # Set slider min/max
        self.min_exposure_us = 100
        self.max_exposure_us = 10000
        self.vsExposure.setMinimum(self.min_exposure_us)
        self.vsExposure.setMaximum(self.max_exposure_us)
        self.vsExposure.setValue(250)
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
            self.btnSnap.setText("Record images")
            self.chkBoxRecord.setEnabled(True)
            self.chkBoxMaxFPS.setEnabled(True)
            sleep(0.1)
            self.acquisitionThread.zw.closeFile()
            self.acquisitionThread.metadata_file.close()
            end_time = perf_counter()
            start_time = self.acquisitionThread.start_time
            num_images = self.acquisitionThread.im_counter
            print(
                f"{num_images} images taken in {end_time - start_time:.2f}s ({num_images / (end_time-start_time):.2f} fps)"
            )

            retval = self._displayMessageBox(QtWidgets.QMessageBox.Icon.Information,
                        "Open Flowcell QC Post-run Form?",
                        "Press okay to open the Google form. A browser window will be opened.",
                        cancel=True
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
        retval = self._displayMessageBox(QtWidgets.QMessageBox.Icon.Information,
                        "Open Flowcell QC Post-run Form?",
                        "Press okay to open the Google form. A browser window will be opened.",
                        cancel=True
                    )
        if retval == QtWidgets.QMessageBox.Ok:
            webbrowser.open(FLOWCELL_QC_FORM_LINK, new=1, autoraise=True)

    def experimentSetupHandler(self):
        self.btnAbortExperiment.setEnabled(True)
        self.experiment_form_dialog.show()

    @pyqtSlot(QImage)
    def updateImage(self, qimage):
        self.lblImage.setPixmap(QPixmap.fromImage(qimage))

    @pyqtSlot(int)
    def updateMotorPosition(self, val):
        self.vsFocus.setValue(val)
        self.txtBoxFocus.setText(f"{val}")

    @pyqtSlot(int)
    def updateSyringePos(self, _):
        self.vsFlow.setValue(self.convertTovsFlowVal(self.pneumatic_module.getCurrentDutyCycle()))
        duty_cycle = self.pneumatic_module.duty_cycle
        self.txtBoxFlow.setText(f"{duty_cycle}")

    @pyqtSlot(float)
    def updatePressureLabel(self, val):
        self.lblPressure.setText(f"{val:.2f} hPa")

    @pyqtSlot(int)
    def updateFPS(self, val):
        self.lblFPS.setText(f"{val}fps")

    @pyqtSlot(int)
    def updateMeasurementTimer(self, val):
        self.lblTimer.setText(f"{str(timedelta(seconds=val))}")

    def btnLEDToggleHandler(self):
        if self.led._isOn:
            self.led.turnOff()
            self.vsLED.blockSignals(True)
            self.vsLED.setEnabled(False)
            self.btnLEDToggle.setText(f"Turn on")
        else:
            self.vsLED.blockSignals(False)
            self.vsLED.setEnabled(True)
            self.led.turnOn()
            self.led.setDutyCycle(int(self.vsLED.value()) / 100)
            self.btnLEDToggle.setText(f"Turn off")

    def btnAutobrightnessHandler(self):
        self.acquisitionThread.autobrightness.reset()
        self.btnAutobrightness.setEnabled(False)
        self.btnLEDToggle.setEnabled(False)
        self.vsLED.blockSignals(True)
        self.vsLED.setEnabled(False)
        self.acquisitionThread.autobrightness_on = True
        self.btnLEDToggle.setText(f"Turn off")

    @pyqtSlot(int)
    def autobrightnessDone(self, val):
        self.btnAutobrightness.setEnabled(True)
        self.btnLEDToggle.setEnabled(True)
        self.vsLED.blockSignals(False)
        self.vsLED.setEnabled(True)
        new_val = self.led.pwm_duty_cycle*100
        self.vsLED.setValue(new_val)
        self.lblLED.setText(f"{int(new_val)}%")

    def vsLEDHandler(self):
        perc = int(self.vsLED.value())
        self.lblLED.setText(f"{int(perc)}%")
        self.led.setDutyCycle(perc / 100)

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
            print(f"Motor already in motion.")

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
            "Press okay to sweep the motor over its entire range and automatically find and move to the focal position.",
            cancel=True,
        )

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runFullZStack(self.motor)

    def btnLocalZStackHandler(self):
        retval = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Information,
            "Local Vicinity ZStack",
            "Press okay to sweep the motor over its current nearby vicinity and move to the focal position.",
            cancel=True,
        )

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runLocalZStack(self.motor, self.motor.pos)

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
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        duty_cycle = self.pneumatic_module.duty_cycle
        self.vsFlow.setValue(self.convertTovsFlowVal(duty_cycle))
        self.txtBoxFlow.setText(f"{duty_cycle}")

    def btnFlowDownHandler(self):
        try:
            self.pneumatic_module.threadedDecreaseDutyCycle()
        except SyringeInMotion:
            # TODO: Change to logging
            print("Syringe already in motion.")
        duty_cycle = self.pneumatic_module.duty_cycle
        self.vsFlow.setValue(self.convertTovsFlowVal(duty_cycle))
        self.txtBoxFlow.setText(f"{duty_cycle}")

    def convertFromvsFlowVal(self):
        return self.vsFlow.value() * self.pneumatic_module.min_step_size + self.pneumatic_module.getMinDutyCycle()
    
    def convertTovsFlowVal(self, val):
        return int((val - self.pneumatic_module.getMinDutyCycle()) / self.pneumatic_module.min_step_size)
    
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
            retval = self._displayMessageBox(
                QtWidgets.QMessageBox.Icon.Information,
                "Active flow control (AFC)",
                f"The AFC will attempt to maintain a the current flow rate. Press okay to confirm.",
                cancel=True,
            )
            if retval == QtWidgets.QMessageBox.Ok:
                self.acquisitionThread.initializeFlowControl = True
                self.disablePressureUIElements()
        else:
            self.acquisitionThread.stopActiveFlowControl()
            self.enablePressureUIElements()

    def enablePressureUIElements(self):
        self.vsFlow.blockSignals(False)
        self.vsFlow.setEnabled(True)
        self.txtBoxFlow.blockSignals(False)
        self.btnFlowUp.setEnabled(True)
        self.btnFlowDown.setEnabled(True)

    def disablePressureUIElements(self):
        self.vsFlow.blockSignals(True)
        self.vsFlow.setEnabled(False)
        self.txtBoxFlow.blockSignals(True)
        self.btnFlowUp.setEnabled(False)
        self.btnFlowDown.setEnabled(False)

    @pyqtSlot(int)
    def pressureLeak(self, _):
        self.chkBoxFlowControl.setChecked(False)
        self.lblTargetPressure.setText("")
        self.enablePressureUIElements()
        _ = self._displayMessageBox(
            QtWidgets.QMessageBox.Icon.Warning,
            "Leak - Active pressure controlled stopped",
            f"The target flowrate can not be attained, stopping active flow control.",
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
            # Close the camera
            self.acquisitionThread.camera.deactivateCamera()

            # Move syringe back and de-energize
            self.pneumatic_module.close()

            # Turn off the LED
            self.led.close()

            # Turn off camera
            if self.acquisitionThread != None and not SIMULATION:
                self.acquisitionThread.camera_activated = False
                self.acquisitionThread.camera.stopAcquisition()
                self.acquisitionThread.camera.deactivateCamera()

            # Turn off encoder
            if self.encoder:
                self.encoder.close()

            quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MalariaScopeGUI()
    main_window.show()
    sys.exit(app.exec_())