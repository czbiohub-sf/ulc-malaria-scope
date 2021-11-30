from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError

from ulc_mm_package.hardware.pim522_rotary_encoder import PIM522RotaryEncoder
from ulc_mm_package.hardware.pressure_control import PressureControl, PressureControlError
from ulc_mm_package.hardware.hardware_constants import ROT_A_PIN, ROT_B_PIN

import sys
import traceback
from time import perf_counter, sleep
from os import path, mkdir
from datetime import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from cv2 import imwrite
import numpy as np

BIG_SCREEN = True
if BIG_SCREEN:
    _UI_FILE_DIR = "liveview_big.ui"
    LABEL_WIDTH = 800
    LABEL_HEIGHT = 600
else:
    _UI_FILE_DIR = "liveview.ui"
    LABEL_WIDTH = 480
    LABEL_HEIGHT = 360

class CameraThread(QThread):
    changePixmap = pyqtSignal(QImage)
    camera_activated = False
    main_dir = None
    single_save = False
    continuous_save = False

    try:
        livecam = ULCMM_Camera()
        livecam.print()
        camera_activated = True
    except CameraError:
        camera_activated = False

    def run(self):
        while self.camera_activated:
            try:
                for image in self.livecam.yieldImages():
                    image = np.flipud(image)
                    self.image = image

                    if self.single_save:
                        filename = path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + ".jpg"
                        imwrite(filename, image)
                        self.single_save = False

                    if self.continuous_save:
                        filename = path.join(self.main_dir, self.continuous_dir_name, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + f"_{self.im_counter}.jpg"
                        if imwrite(filename, image):
                            self.im_counter += 1
                    
                    h, w = image.shape
                    qimage = QImage(image, w, h, QImage.Format_Grayscale8)
                    qimage = qimage.scaled(LABEL_WIDTH, LABEL_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.changePixmap.emit(qimage)
            except Exception as e:
                # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                # Once that happens, this can be swapped to catch the PyCameraException
                print(e)
                print(traceback.format_exc())

    def updateExposure(self, exposure):
        self.livecam.exposureTime_ms = exposure

    def takeImage(self):
        if self.main_dir == None:
            self.main_dir = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
            mkdir(self.main_dir)

        if self.continuous_save:
            self.continuous_dir_name = datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
            mkdir(path.join(self.main_dir, self.continuous_dir_name))
            self.start_time = perf_counter()
            self.im_counter = 0

class CameraStream(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(CameraStream, self).__init__(*args, **kwargs)
        
        # List hardware components
        self.cameraThread = None
        self.motor = None
        self.pressure_control = None
        self.encoder = None
        self.led = None

        # Load the ui file 
        uic.loadUi(_UI_FILE_DIR, self)

        self.showFullScreen()

        # Start the video stream
        self.cameraThread = CameraThread()
        self.cameraThread.start()
        self.recording = False
        
        if not self.cameraThread.camera_activated:
            print(f"Error initializing Basler camera. Disabling camera GUI elements.")
            self.btnSnap.setEnabled(False)
            self.chkBoxRecord.setEnabled(False)
            self.txtBoxExposure.setEnabled(False)
            self.vsExposure.setEnabled(False)

        # Create the LED
        try:
            self.led = LED_TPS5420TDDCT()
            self.led.setDutyCycle(0.5)
        except LEDError:
            print("Error instantiating LED. Continuing...")

        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema()
            self.motor.homeToLimitSwitches()

        except MotorControllerError:
            print("Error initializing DRV8825. Disabling focus actuation GUI elements.")
            self.btnFocusUp.setEnabled(False)
            self.btnFocusDown.setEnabled(False)
            self.vsFocus.setEnabled(False)
            self.txtBoxFocus.setEnabled(False)
        
        # Create pressure controller (sensor + servo)
        try:
            self.pressure_control = PressureControl()
            self.vsFlow.setMinimum(self.pressure_control.getMinDutyCycle())
            self.vsFlow.setValue(self.pressure_control.getCurrentDutyCycle())
            self.lblMinFlow.setText(f"{self.pressure_control.getMinDutyCycle()}")
            self.vsFlow.setMaximum(self.pressure_control.getMaxDutyCycle())
            self.lblMaxFlow.setText(f"{self.pressure_control.getMaxDutyCycle()}")
            self.vsFlow.setTickInterval(self.pressure_control.min_step_size)
            self.txtBoxFlow.setText(f"{self.pressure_control.getCurrentDutyCycle()}")
        except PressureControlError:
            print("Error initializing Pressure Controller. Disabling flow GUI elements.")
            # self.btnFlowUp.setEnabled(False)
            # self.btnFlowDown.setEnabled(False)
            # self.vsFlow.setEnabled(False)
            # self.txtBoxFlow.setEnabled(False)

        ### Connect UI elements to actions ###

        # Camera
        self.cameraThread.changePixmap.connect(self.updateImage)
        self.txtBoxExposure.textChanged.connect(self.exposureTextBoxHandler)
        self.chkBoxRecord.stateChanged.connect(self.checkBoxHandler)
        self.btnSnap.clicked.connect(self.btnSnapHandler)
        self.vsExposure.valueChanged.connect(self.exposureSliderHandler)
        
        # Pressure control
        self.btnFlowUp.clicked.connect(self.btnFlowUpHandler)
        self.btnFlowDown.clicked.connect(self.btnFlowDownHandler)
        self.txtBoxFlow.textChanged.connect(self.flowTextBoxHandler)
        self.vsFlow.valueChanged.connect(self.vsFlowHandler)

        # Misc
        self.btnExit.clicked.connect(self.exit)

        # Set slider min/max
        min_exposure_us = 100
        max_exposure_us = 10000
        self.vsExposure.setMinimum(min_exposure_us) 
        self.vsExposure.setMaximum(max_exposure_us)
        self.vsExposure.setValue(500)
        self.lblMinExposure.setText(f"{min_exposure_us} us")
        self.lblMaxExposure.setText(f"{max_exposure_us} us")

    def checkBoxHandler(self):
        if self.chkBoxRecord.checkState():
            # Continuously record images to a new subfolder
            self.btnSnap.setText("Record images")
        else:
            self.btnSnap.setText("Take image")

    def btnSnapHandler(self):
        if self.recording:
            self.recording = False
            self.cameraThread.continuous_save = False
            self.btnSnap.setText("Record images")
            self.chkBoxRecord.setEnabled(True)
            end_time = perf_counter()
            start_time = self.cameraThread.start_time
            num_images = self.cameraThread.im_counter
            print(f"{num_images} taken in {end_time - start_time} ({num_images / (end_time-start_time)} fps)")
            return

        if self.chkBoxRecord.checkState():
            self.cameraThread.continuous_save = True
            self.btnSnap.setText("Stop recording")
            self.recording = True
            self.chkBoxRecord.setEnabled(False)
            self.cameraThread.takeImage()
        else:
            self.cameraThread.single_save = True
            self.cameraThread.takeImage()

    @pyqtSlot(QImage)
    def updateImage(self, image):
        self.lblImage.setPixmap(QPixmap.fromImage(image))

    def exposureSliderHandler(self):
        exposure = int(self.vsExposure.value())
        self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        self.txtBoxExposure.setText(f"{exposure}")

    def exposureTextBoxHandler(self):
        try:
            exposure = int(float(self.txtBoxExposure.text()))
        except:
            print("Error parsing textbox exposure time input. Continuing...")
            return
        try:
            self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        except:
            print("Invalid exposure, ignoring and continuing...")
            return
        self.vsExposure.setValue(exposure)

    def btnFlowUpHandler(self):
        self.pressure_control.increaseDutyCycle()
        duty_cycle = self.pressure_control.duty_cycle
        self.vsFlow.setValue(duty_cycle)
        self.txtBoxFlow.setText(f"{duty_cycle}")

    def btnFlowDownHandler(self):
        self.pressure_control.decreaseDutyCycle()
        duty_cycle = self.pressure_control.duty_cycle
        self.vsFlow.setValue(duty_cycle)
        self.txtBoxFlow.setText(f"{duty_cycle}")

    def vsFlowHandler(self):
        flow_duty_cycle = int(self.vsFlow.value())
        self.pressure_control.setDutyCycle(flow_duty_cycle)
        self.txtBoxFlow.setText(f"{flow_duty_cycle}")

    def flowTextBoxHandler(self):
        try:
            flow_duty_cycle = int(float(self.txtBoxFlow.text()))
        except:
            print("Error parsing textbox flow PWM input. Continuing...")
            return

        try:
            self.pressure_control.setDutyCycle(flow_duty_cycle)
        except:
            print("Invalid duty cycle, ignoring and continuing...")
            return
        
        self.vsFlow.setValue(flow_duty_cycle)

    def manualFocusWithEncoder(self, increment: int):
        if increment == 1:
            self.motor.motor_go(dir=Direction.CW, steps=1)
        elif increment == -1:
            self.motor.motor_go(dir=Direction.CCW, steps=1)
        sleep(0.01)

    def changeExposureWithEncoder(self, increment):
        if increment == 1:
            self.vsExposure.setValue(self.vsExposure.value() + 10)
        elif increment == -1:
            self.vsExposure.setValue(self.vsExposure.value() - 10)
        sleep(0.01)

    def exit(self):
        # Move syringe back and de-energize
        if self.pressure_control != None:
            self.pressure_control.setDutyCycle(self.pressure_control.getMinDutyCycle())
        # Turn off camera
        if self.cameraThread != None:
            self.cameraThread.camera_activated = False
        quit()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main_window = CameraStream()
    main_window.show()
    sys.exit(app.exec_())