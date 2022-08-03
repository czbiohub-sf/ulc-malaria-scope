import argparse 

# Select operation mode
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--sim', action='store_true', help="simulation mode")
mode = parser.parse_args()

# Use real hardware objects
if not mode.sim:
    from ulc_mm_package.hardware.camera import CameraError, BaslerCamera, AVTCamera
    from ulc_mm_package.hardware.motorcontroller import (
        DRV8825Nema,
        Direction,
        MotorControllerError,
        MotorInMotion,
    )
    from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError
    from ulc_mm_package.hardware.pim522_rotary_encoder import PIM522RotaryEncoder
    from ulc_mm_package.hardware.pressure_control import (
        PressureControl,
        PressureControlError,
        PressureLeak,
    )
    from ulc_mm_package.hardware.fan import Fan

# Use simulated hardware objects
else:
    from ulc_mm_package.hardware.simulation import *

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
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from cv2 import imwrite
from qimage2ndarray import array2qimage

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
_UI_FILE_DIR = "expUI.ui"
DEFAULT_SSD = "/media/pi/"
ALT_SSD = "./sim_media/pi/"
_EXPERIMENT_FORM_PATH = "experimentform.ui"

class AcquisitionThread(QThread):
    # Qt signals must be defined at the class-level (not instance-level)

    # NOTE for runtime operation
    changePixmap = pyqtSignal(QImage)
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
            print("ERROR: Camera could not be activated.")
            quit()

    def run(self):
        while True:
            if self.setup_done:
                try:
                    for image in self.camera.yieldImages():
                        self.updateGUIElements()
                        self.save(image)
                        self.zStack(image)
                        self.activeFlowControl(image)
                        self._autobrightness(image)

                except PyCameraException as e:
                # except Exception as e:
                    # TODO remove below comments if this is working
                    # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                    # Once that happens, this can be swapped to catch the PyCameraException
                    self.abort(e + "\n" + traceback.format_exc())
                    # print(e)
                    # print(traceback.format_exc())

            else:
                # TODO implement this
                pass

    # TODO test this
    def abort(self, message):
        print(message)
        quit()

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
                    self.abort("ERROR: Could not read pressure")
            self.fps.emit(int(self.pressure_update_loops / (perf_counter() - self.fps_timer)))
            self.fps_timer = perf_counter()

        # Always maximize fps for image acquisition
        if self.update_counter % self.liveview_update_loops == 0:
            qimage = array2qimage(image)
            self.changePixmap.emit(qimage)

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
            except ValueError:
                # Occurs if an image is sent while the function is still moving the motor
                pass

    # NOTE ################# RUNNING AUTO BRIGHTNESS

    def _autobrightness(self, img: np.ndarray):
        try:
            done = self.autobrightness.runAutobrightness(img)
        except AutobrightnessError as e:
            self.abort("ERROR: Could not enable autobrightness\n" + e)

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
            
class ExperimentSetupGUI(QtWidgets.QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        super(ExperimentSetupGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_EXPERIMENT_FORM_PATH, self)

        # Set the focus order
        #### TODO choose what to do here later
        # self.setTabOrder(self.txtExperimentName, self.txtFlowCellID)
        # self.setTabOrder(self.txtFlowCellID, self.radBtn1x1)
        # self.txtExperimentName.setFocus()

        # Parameters
        self.flowcell_id = ""
        # TODO choose binning mode later
        self.binningMode = 2

    def getAllParameters(self) -> Dict:
        return {
            "flowcell_id": self.flowcell_id,
            "binningMode": self.binningMode,
        }

class MalariaScopeGUI(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        media_dir = DEFAULT_SSD

        if mode.sim:
            print("---------------------\n|  SIMULATION MODE  |\n---------------------")

            if not path.exists(VIDEO_PATH):
                print("Error - no sample video exists. To add your own video, save it under " 
                        + VIDEO_PATH  + "\nRecommended video: " + VIDEO_REC )
                quit()

            if not path.exists(media_dir):
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
        self.pressure_control = None
        self.encoder = None
        self.led = None
        self.fan = Fan()

        # Load the ui file
        uic.loadUi(_UI_FILE_DIR, self)

        # Experiment parameter form dialog
        self.experiment_form_dialog = ExperimentSetupGUI(self)

        # Start the video stream
        self.acquisitionThread = AcquisitionThread(self.external_dir)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MalariaScopeGUI()
    main_window.show()
    sys.exit(app.exec_())
