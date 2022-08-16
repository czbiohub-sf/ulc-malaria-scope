if __name__ == "__main__":
    # Select operation mode
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--sim', action='store_true', help="simulation mode")
    parser.add_argument('-d', '--dev', action='store_true', help="developer mode")
    mode = parser.parse_args()

    if not mode.sim:
        # Use real hardware objects
        from ulc_mm_package.hardware.hardware_list import *
    else: 
        # Use simulated hardware objects
        from ulc_mm_package.hardware.simulation import *

else:
    from ulc_mm_package.hardware.hardware_list import *

from ulc_mm_package.image_processing.zarrwriter import ZarrWriter
from ulc_mm_package.image_processing.autobrightness import Autobrightness, AutobrightnessError

from ulc_mm_package.image_processing.zstack import (
    takeZStackCoroutine,
    symmetricZStackCoroutine,
)

import sys
import csv
import traceback
import numpy as np

from typing import Dict
from time import perf_counter, sleep
from os import listdir, mkdir, path
from datetime import datetime, timedelta
from PyQt5 import uic        # TODO DELETE THIS 
# TODO organize these imports
from PyQt5.QtWidgets import (
    QDialog, QMessageBox,
    QMainWindow, QApplication, QGridLayout, 
    QTabWidget, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QIcon
from cv2 import imwrite
from qimage2ndarray import array2qimage

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
ICON_PATH = "CZB-logo.png"
_EXPERIMENT_FORM_PATH = "user_form.ui"
VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

# ================ SSD constants ================ #
DEFAULT_SSD = "/media/pi/"
ALT_SSD = "./sim_media/pi/"

# TODO test out all dialog boxes

class AcquisitionThread(QThread):
    # Qt signals must be defined at the class-level (not instance-level)

    # NOTE for runtime operation
    changePixmap = pyqtSignal(QImage)
    zStackFinished = pyqtSignal(int)
    updatePressure = pyqtSignal(float)
    measurementTime = pyqtSignal(int)
    fps = pyqtSignal(int)
    pressureLeakDetected = pyqtSignal(int)

    # NOTE for setup operation
    autobrightnessDone = pyqtSignal(int)

    def __init__(self, external_dir):
        super().__init__()

        # NOTE basic operation parameters
        self.im_counter = 0
        self.update_counter = 0
        self.pressure_update_loops = 50
        self.liveview_update_loops = 45   # TODO check if this maximizes fps for image acquisition
        self.setup_done = True      # TODO implement this
        # NOTE basic operation objects
        self.fps_timer = perf_counter()


        # NOTE task parameters #
        # NOTE saving data
        self.main_dir = None 
        self.file_prefix = ""  
        self.external_dir = external_dir

        # NOTE task objects #
        # NOTE zstack in process
        self.takeZStack = False 
        # self.custom_image_prefix = ""
        self.file_prefix = ""   # TODO replaces custom_image_prefix
        # NOTE pressure control object
        self.pressure_control: PressureControl = None
        self.initializeFlowControl = False
        self.flowcontrol_enabled = False
        # NOTE motor object
        self.motor = None
        # NOTE writer object + parameters
        self.zw = ZarrWriter()
        self.md_writer = None
        self.metadata_file = None
        # NOTE autobrightness object
        self.autobrightness: Autobrightness = None
        # NOTE camera object
        try:
            self.camera = BaslerCamera()
        except CameraError as e:
            print("ERROR - Camera could not be activated.")
            quit()

    def run(self):
        while True:
            if self.setup_done:
                try:
                    for image in self.camera.yieldImages():

                        self.updateGUIElements()
                        # TODO add some kind of save here
                        # self.save(image)
                        self.zStack(image)
                        self.activeFlowControl(image)
                        if not mode.sim:
                            self._autobrightness(image)

                        # Always maximize fps for image acquisition
                        if self.update_counter % self.liveview_update_loops == 0:
                            qimage = array2qimage(image)
                            self.changePixmap.emit(qimage)

                # except PyCameraException as e:
                except Exception as e:
                    # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                    # Once that happens, this can be swapped to catch the PyCameraException
                    print(e)
                    print(traceback.format_exc())
                    quit()
                    # print(e)
                    # print(traceback.format_exc())

            else:
                # TODO implement this
                pass

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
            "pressure_hpa": self.pressure_control.getPressure(),
            "syringe_pos": self.pressure_control.getCurrentDutyCycle(),
            "flowrate_target": self.pressure_control.flowrate_target,
            "current_flowrate": self.pressure_control.flow_rate_y,
        }

    def updateGUIElements(self):
        self.update_counter += 1

        if self.update_counter % self.pressure_update_loops == 0:
            self.update_counter = 0
            if self.pressure_control != None:
                try:
                    pressure = self.pressure_control.getPressure()
                    self.updatePressure.emit(pressure)
                except Exception:
                    print("ERROR - Could not read pressure")
                    quit()
            self.fps.emit(int(self.pressure_update_loops / (perf_counter() - self.fps_timer)))
            self.fps_timer = perf_counter()

    # NOTE ############### RUNNING ZSTACK

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
            except StopIteration:
                self.takeZStack = False
                self.zStackFinished.emit(1)
            except ValueError:
                # Occurs if an image is sent while the function is still moving the motor
                pass

    # NOTE ################# RUNNING AUTO BRIGHTNESS

    def _autobrightness(self, img: np.ndarray):
        try:
            done = self.autobrightness.runAutobrightness(img)
        except AutobrightnessError as e:
            print("ERROR - Could not enable autobrightness\n") 
            print(e)
            quit()

    # NOTE ################# RUNNING ZSTACK

    def initializeActiveFlowControl(self, img: np.ndarray):
        self.pressure_control.initializeActiveFlowControl(img)
        self.flowcontrol_enabled = True
        self.initializeFlowControl = False

    # TODO get rid of this if not necessary for shutoff
    def stopActiveFlowControl(self):
        self.flowcontrol_enabled = False
        self.pressure_control.flow_rate_y = 0

    def activeFlowControl(self, img: np.ndarray):
        if self.initializeFlowControl:
            self.initializeActiveFlowControl(img)

        if self.flowcontrol_enabled:
            try:
                self.pressure_control.activeFlowControl(img)
                self.syringePosChanged.emit(1)
            except PressureLeak:
                print(
                    f"""The syringe is already at its maximum position but the current flow rate is either above or below the target.\n
                        Active flow control is now disabled.
                        """         
                )       
                self.pressureLeakDetected.emit(1)
            
class ExperimentSetupGUI(QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        super(ExperimentSetupGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_EXPERIMENT_FORM_PATH, self)

        # Set the focus order
        self.setTabOrder(self.txtExperimentName, self.txtFlowCellID)
        self.setTabOrder(self.txtFlowCellID, self.btnStartExperiment)
        self.txtExperimentName.setFocus()

        # Parameters
        self.flowcell_id = ""
        self.experiment_name = ""
        # TODO choose binning mode later
        self.binningMode = 2

        # Set up event handlers
        self.btnExperimentSetupAbort.clicked.connect(quit)

    def getAllParameters(self) -> Dict:
        return {
            "flowcell_id": self.flowcell_id,
            "experiment_name": self.experiment_name,
            "binningMode": self.binningMode,
        }


    # def _displayMessageBox(self, icon, title, text, cancel):

    #     msgBox = QMessageBox()
    #     msgBox.setIcon(icon)
    #     msgBox.setWindowTitle(f"{title}")
    #     msgBox.setText(f"{text}")
    #     if cancel:
    #         msgBox.setStandardButtons(
    #             QMessageBox.Ok | QMessageBox.Cancel
    #         )
    #     else:
    #         msgBox.setStandardButtons(QMessageBox.Ok)
    #     return msgBox.exec()

class MalariaScopeGUI(QMainWindow):

    def __init__(self, *args, **kwargs):

        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        media_dir = DEFAULT_SSD
        if mode.sim:
            if not path.exists(VIDEO_PATH):
                retval = self._displayMessageBox(
                    QMessageBox.Icon.Critical,
                    "Missing sample video",
                    "Sample video must be saved to " + VIDEO_PATH  
                        + "\n\nRecommended video: " + VIDEO_REC
                        + "\n\nPress OK to close the application.",
                    cancel=False,
                )
                if retval == QMessageBox.Ok:
                    quit()

            if not path.exists(media_dir):
                media_dir = ALT_SSD
                print("No external harddrive / SSD. Saving media to local directory " + media_dir + " instead.")

        try:
            self.external_dir = media_dir + listdir(media_dir)[0] + "/"
        except IndexError:
            retval = self._displayMessageBox(
                QMessageBox.Icon.Critical,
                "Harddrive / SSD not detected",
                "No external harddrive / SSD detected. Press OK to close the application.",
                cancel=False,
            )
            if retval == QMessageBox.Ok:
                quit()

        # List hardware components
        self.acquisitionThread = None
        self.motor = None
        self.pressure_control = None
        self.encoder = None
        self.led = None
        self.fan = Fan()

        # Load the ui
        self._loadUI()

        # Start the video stream
        self.acquisitionThread = AcquisitionThread(self.external_dir)

        try:
            self.led = LED_TPS5420TDDCT()
            self.led.turnOn()
            self.led.setDutyCycle(0)

        except LEDError:
            retval = self._displayMessageBox(
                QMessageBox.Icon.Critical,
                "LED error",
                "Could not instantiate LED.",
                cancel=False,
            )
            if retval == QMessageBox.Ok:
                quit()

        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema(steptype="Half")
            self.motor.homeToLimitSwitches()
            print("Moving motor to the middle.")
            sleep(0.5)
            self.motor.move_abs(int(self.motor.max_pos // 2))

        except MotorControllerError:
            retval = self._displayMessageBox(
                QMessageBox.Icon.Critical,
                "Motor error",
                "Could not instantiate motor controller.",
                cancel=False,
            )
            if retval == QMessageBox.Ok:
                quit()

        # Create pressure controller (sensor + servo)
        try:
            self.pressure_control = PressureControl()
            # TODO include relevant info
            # self.txtBoxFlow.setText(f"{self.pressure_control.getCurrentDutyCycle()}")
        except PressureControlError:
            retval = self._displayMessageBox(
                QMessageBox.Icon.Critical,
                "Pressure error",
                "Could not instantiate pressure controller.",
                cancel=False,
            )
            if retval == QMessageBox.Ok:
                quit()

        # Connect the encoder
        try:
            self.encoder = PIM522RotaryEncoder(self.manualFocusWithEncoder)
        except EncoderI2CError as e:
            retval = self._displayMessageBox(
                QMessageBox.Icon.Critical,
                "Encoder error",
                "Could not instantiate encoder.",
                cancel=False,
            )
            if retval == QMessageBox.Ok:
                quit()

        # Acquisition thread      # TODO sort this out
        self.acquisitionThread.changePixmap.connect(self.updateImage)
        self.acquisitionThread.fps.connect(self.updateHardwareLbl)
        self.acquisitionThread.autobrightnessDone.connect(self.autobrightnessDone)

        self.acquisitionThread.motor = self.motor
        self.acquisitionThread.pressure_control = self.pressure_control
        self.acquisitionThread.autobrightness = Autobrightness(self.led)

        # Acquisition thread settings
        self.acquisitionThread.update_liveview = 1
        # self.acquisitionThread.update_liveview = 45

        self.acquisitionThread.start()

        # Misc
        self.fan.turn_on()
        self.exit_btn.clicked.connect(self.exit)

    def _displayMessageBox(self, icon, title, text, cancel):
        msgBox = QMessageBox()
        msgBox.setWindowIcon(QIcon(ICON_PATH))
        msgBox.setIcon(icon)
        msgBox.setWindowTitle(f"{title}")
        msgBox.setText(f"{text}")
        if cancel:
            msgBox.setStandardButtons(
                QMessageBox.Ok | QMessageBox.Cancel
            )
        else:
            msgBox.setStandardButtons(QMessageBox.Ok)
        return msgBox.exec()

    def _loadUI(self):
        self.setWindowTitle('Malaria Scope')
        self.setGeometry(100, 100, 1100, 700)
        self.show()

        # Set up central layout + widget
        self.main_layout = QGridLayout()
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(self.main_layout)

        # Set up liveview layout + widget
        self.liveview_layout = QHBoxLayout()
        self.liveview_widget = QWidget()
        self.liveview_widget.setLayout(self.liveview_layout)

        # Populate liveview tab
        self.margin_layout = QVBoxLayout()
        self.margin_widget = QWidget()
        self.margin_widget.setLayout(self.margin_layout)

        self.liveview_img = QLabel()
        self.status_lbl = QLabel("Setup")
        self.timer_lbl = QLabel("Timer")
        self.exit_btn = QPushButton("Exit")
        self.info_lbl = QLabel()
        self.hardware_lbl = QLabel()

        self.liveview_img.setAlignment(Qt.AlignCenter)
        self.status_lbl.setAlignment(Qt.AlignHCenter)
        self.timer_lbl.setAlignment(Qt.AlignHCenter)

        # TODO
        # resize camera feed as necessary
        # set minimum column width as necessary
        # fix initial pixmap size absed on camera feed

        self.liveview_layout.addWidget(self.liveview_img)
        self.liveview_layout.addWidget(self.margin_widget)

        self.margin_layout.addWidget(self.status_lbl)
        self.margin_layout.addWidget(self.timer_lbl)
        self.margin_layout.addWidget(self.exit_btn)
        self.margin_layout.addWidget(self.info_lbl)
        self.margin_layout.addWidget(self.hardware_lbl)

        # Set up thumbnail layout + widget
        self.thumbnail_layout = QGridLayout()
        self.thumbnail_widget = QWidget()
        self.thumbnail_widget.setLayout(self.thumbnail_layout)

        # Populate thumbnail tab
        self.ring_lbl = QLabel("Ring")
        self.troph_lbl = QLabel("Troph")
        self.schizont_lbl = QLabel("Schizont")
        self.ring_img = QLabel()
        self.troph_img = QLabel()
        self.schizont_img = QLabel()

        self.ring_lbl.setAlignment(Qt.AlignHCenter)
        self.troph_lbl.setAlignment(Qt.AlignHCenter)
        self.schizont_lbl.setAlignment(Qt.AlignHCenter)

        self.ring_img.setScaledContents(True)
        self.troph_img.setScaledContents(True)
        self.schizont_img.setScaledContents(True)

        self.thumbnail_layout.addWidget(self.ring_lbl, 0, 0)
        self.thumbnail_layout.addWidget(self.troph_lbl, 0, 1)
        self.thumbnail_layout.addWidget(self.schizont_lbl, 0, 2)
        self.thumbnail_layout.addWidget(self.ring_img, 1, 0)
        self.thumbnail_layout.addWidget(self.troph_img, 1, 1)
        self.thumbnail_layout.addWidget(self.schizont_img, 1, 2)

        # Set up tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.liveview_widget, "Liveviewer")
        self.tab_widget.addTab(self.thumbnail_widget, "Parasite Thumbnail")
        self.main_layout.addWidget(self.tab_widget, 0, 0)

    def _setup(self):
        pass

    @pyqtSlot(QImage)
    def updateImage(self, qimage):
        self.liveview_img.setPixmap(QPixmap.fromImage(qimage))

        # # TODO implement parasite thumbnails
        # self.ring_img.setPixmap(QPixmap.fromImage(qimage))
        # self.troph_img.setPixmap(QPixmap.fromImage(qimage))
        # self.schizont_img.setPixmap(QPixmap.fromImage(qimage))

    @pyqtSlot(int)
    def autobrightnessDone(self, val):
        self.btnAutobrightness.setEnabled(True)
        self.btnLEDToggle.setEnabled(True)
        self.vsLED.blockSignals(False)
        self.vsLED.setEnabled(True)
        new_val = int(self.led._convertPWMValToDutyCyclePerc(self.led.pwm_duty_cycle)*100)
        self.vsLED.setValue(new_val)
        self.lblLED.setText(f"{new_val}%")

    @pyqtSlot(int)
    def pressureLeak(self, _):
        self.chkBoxFlowControl.setChecked(False)
        self.lblTargetPressure.setText("")
        self.enablePressureUIElements()
        _ = self._displayMessageBox(
            QMessageBox.Icon.Critical,
            "Pressure leak",
            """The target flowrate can not be attained. Stopping active flow control. 
                \n\nPress OK to close the application.""",
            cancel=False,
        )

    @pyqtSlot(int)
    def updateHardwareLbl(self, fps):
        self.hardware_lbl.setText(f"FPS: {fps}")

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
            QMessageBox.Icon.Information,
            "Exit application",
            """Please remove the flow cell now. 
                \n\nOnly press OK after the flow cell has been removed,
                as the syringe will move into the topmost position.""",
            cancel=True,
        )

        if retval == QMessageBox.Ok:
            # Move syringe back and de-energize
            self.pressure_control.close()

            # Turn off the LED
            self.led.close()

            # Turn off camera
            if self.acquisitionThread != None and not mode.sim:
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

class WindowManager():
    def __init__(self):
        self.setup_window = ExperimentSetupGUI()
        self.setup_window.setWindowIcon(QIcon(ICON_PATH))
        self.setup_window.show()

        # Set up event handler
        self.setup_window.btnStartExperiment.clicked.connect(self.btnStartExperimentHandler)

    def btnStartExperimentHandler(self):

        self.setup_window.experiment_name = self.setup_window.txtExperimentName.text()
        self.setup_window.flowcell_id = self.setup_window.txtFlowCellID.text()

        # TODO switch this to close() if getAllParameters() doesn't need to be called
        self.setup_window.hide()

        self.main_window = MalariaScopeGUI()
        self.main_window.setWindowIcon(QIcon(ICON_PATH))
        self.main_window.show()

        # if not self.setup_window.experiment_name or not self.setup_window.flowcell_id:
        #     retval = self.setup_window._displayMessageBox(
        #         QMessageBox.Icon.Warning,
        #         "Empty form entries",
        #         "Please fill out all entries before proceeding.",
        #         cancel=False,
        #     )

        # else:
            # # TODO switch this to close() if getAllParameters() doesn't need to be called
            # self.setup_window.hide()

            # self.main_window = MalariaScopeGUI()
            # self.main_window.setWindowIcon(QIcon(ICON_PATH))
            # self.main_window.show()


if __name__ == "__main__":

    if mode.sim:
        print("---------------------\n|  SIMULATION MODE  |\n---------------------")

    app = QApplication(sys.argv)
    manager = WindowManager()
    sys.exit(app.exec_())