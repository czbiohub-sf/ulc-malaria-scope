from re import S
from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError
from ulc_mm_package.hardware.pim522_rotary_encoder import PIM522RotaryEncoder
from ulc_mm_package.hardware.pressure_control import PressureControl, PressureControlError
from ulc_mm_package.hardware.hardware_constants import ROT_A_PIN, ROT_B_PIN
from ulc_mm_package.hardware.zarrwriter import ZarrWriter

from ulc_mm_package.image_processing.zstack import takeZStackCoroutine

import sys
import traceback
from time import perf_counter, sleep
from os import path, mkdir
from datetime import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
import cv2
import numpy as np
from qimage2ndarray import gray2qimage

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
BIG_SCREEN = True
MIN_EXPOSURE_US = 100
EXTERNAL_DIR = "/media/pi/T7/"
WRITE_NUMPY = True

if BIG_SCREEN:
    _UI_FILE_DIR = "liveview_big.ui"
    LABEL_WIDTH = 1307
    LABEL_HEIGHT = 980
else:
    _UI_FILE_DIR = "liveview.ui"
    LABEL_WIDTH = 480
    LABEL_HEIGHT = 360

class CameraThread(QThread):
    changePixmap = pyqtSignal(QImage)
    motorPosChanged = pyqtSignal(int)
    zStackFinished = pyqtSignal(int)
    updatePressure = pyqtSignal(float)
    fps = pyqtSignal(int)
    update_liveview = 1
    update_counter = 0
    num_loops = 50
    camera_activated = False
    main_dir = None
    single_save = False
    continuous_save = False
    liveview = True
    takeZStack = False
    continuous_dir_name = None
    custom_image_prefix = ''
    zarr_writer = ZarrWriter()
    pressure_sensor = None

    try:
        livecam = ULCMM_Camera()
        camera_activated = True
    except CameraError:
        camera_activated = False

    def run(self):
        while True:
            if self.camera_activated:
                start = perf_counter()
                try:
                    for image in self.livecam.yieldImages():
                        self.update_counter += 1
                        if self.update_counter % self.num_loops == 0:
                            self.update_counter = 0
                            if self.pressure_sensor != None:
                                self.updatePressure.emit(self.pressure_sensor.pressure)
                            self.fps.emit(int(self.num_loops / (perf_counter() - start)))
                            start = perf_counter()

                        if self.single_save:
                            filename = path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + f"{self.custom_image_prefix}.tiff"
                            cv2.imwrite(filename, image)
                            self.single_save = False

                        if self.continuous_save and self.continuous_dir_name != None:
                            filename = path.join(self.main_dir, self.continuous_dir_name, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + f"{self.custom_image_prefix}{self.im_counter:05}"
                            if WRITE_NUMPY:
                                np.save(filename+".npy", image)
                            else:
                                cv2.imwrite(filename+".tiff", image)
                            self.im_counter += 1
                        
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

                        if self.liveview and self.update_counter % self.update_liveview == 0:
                            qimage = gray2qimage(image)
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
            self.main_dir = EXTERNAL_DIR + datetime.now().strftime("%Y-%m-%d-%H%M%S")
            mkdir(self.main_dir)

        if self.continuous_save:
            self.continuous_dir_name = datetime.now().strftime("%Y-%m-%d-%H%M%S") + f"{self.custom_image_prefix}"
            mkdir(path.join(self.main_dir, self.continuous_dir_name))
            self.start_time = perf_counter()
            self.im_counter = 0

    def changeBinningMode(self):
        if self.camera_activated:
            self.livecam.stopAcquisition()
            self.camera_activated = False
        
        if self.livecam.camera.BinningHorizontal.GetValue() == 2:
            print("Changing to 1x1 binning.")
            self.binning = 1
            self.livecam.setBinning(bin_factor=1, mode="Average")
        else:
            print("Changing to 2x2 binning.")
            self.binning = 2
            self.livecam.setBinning(bin_factor=2, mode="Average")
        
        self.camera_activated = True
    
    def runZStack(self, motor):
        self.takeZStack = True
        self.motor = motor
        self.zstack = takeZStackCoroutine(None, motor)
        self.zstack.send(None)

class CameraStream(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(CameraStream, self).__init__(*args, **kwargs)
        
        # List hardware components
        self.cameraThread = None
        self.motor = None
        self.pressure_control = None
        self.encoder = PIM522RotaryEncoder(self.manualFocusWithEncoder)
        self.led = None

        # Load the ui file 
        uic.loadUi(_UI_FILE_DIR, self)

        # self.showMaximized()

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
            self.led.setDutyCycle(0)
            self.vsLED.setValue(0)
            self.lblLED.setText(f"{int(self.vsLED.value())}%")
            self.vsLED.valueChanged.connect(self.vsLEDHandler)
        except LEDError:
            print("Error instantiating LED. Continuing...")

        # Create motor w/ default pins/settings (full step)
        try:
            self.motor = DRV8825Nema(steptype="Half")
            self.motor.homeToLimitSwitches()
            while not self.motor.homed:
                pass
            sleep(0.5)
            self.lblFocusMax.setText(f"{self.motor.max_pos}")

            self.btnFocusUp.clicked.connect(self.btnFocusUpHandler)
            self.btnFocusDown.clicked.connect(self.btnFocusDownHandler)
            self.vsFocus.sliderReleased.connect(self.vsFocusHandler)
            self.txtBoxFocus.editingFinished.connect(self.focusTextBoxHandler)
            self.btnZStack.clicked.connect(self.btnZStackHandler)
            self.vsFocus.setMinimum(self.motor.pos)
            self.vsFocus.setValue(self.motor.pos)
            self.vsFocus.setMaximum(self.motor.max_pos)

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
            self.lblMinFlow.setText(f"{self.pressure_control.getMinDutyCycle()}")
            self.vsFlow.setMaximum(self.pressure_control.getMaxDutyCycle())
            self.lblMaxFlow.setText(f"{self.pressure_control.getMaxDutyCycle()}")
            self.vsFlow.setTickInterval(self.pressure_control.min_step_size)
            self.txtBoxFlow.setText(f"{self.pressure_control.getCurrentDutyCycle()}")
            self.vsFlow.setValue(self.pressure_control.getCurrentDutyCycle())
        except PressureControlError:
            print("Error initializing Pressure Controller. Disabling flow GUI elements.")
            self.btnFlowUp.setEnabled(False)
            self.btnFlowDown.setEnabled(False)
            self.vsFlow.setEnabled(False)
            self.txtBoxFlow.setEnabled(False)

        ### Connect UI elements to actions ###

        # Acquisition thread
        self.cameraThread.changePixmap.connect(self.updateImage)
        self.cameraThread.motorPosChanged.connect(self.updateMotorPosition)
        self.cameraThread.zStackFinished.connect(self.zStackFinished)
        self.cameraThread.updatePressure.connect(self.updatePressureLabel)
        self.cameraThread.fps.connect(self.updateFPS)
        self.cameraThread.pressure_sensor = self.pressure_control.mpr
        self.txtBoxExposure.editingFinished.connect(self.exposureTextBoxHandler)
        self.chkBoxRecord.stateChanged.connect(self.checkBoxRecordHandler)
        self.chkBoxMaxFPS.stateChanged.connect(self.checkBoxMaxFPSHandler)
        self.btnSnap.clicked.connect(self.btnSnapHandler)
        self.vsExposure.valueChanged.connect(self.exposureSliderHandler)
        self.btnChangeBinning.clicked.connect(self.btnChangeBinningHandler)

        # Pressure control
        self.btnFlowUp.clicked.connect(self.btnFlowUpHandler)
        self.btnFlowDown.clicked.connect(self.btnFlowDownHandler)
        self.txtBoxFlow.editingFinished.connect(self.flowTextBoxHandler)
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

    def checkBoxRecordHandler(self):
        if self.chkBoxRecord.checkState():
            # Continuously record images to a new subfolder
            self.btnSnap.setText("Record images")
        else:
            self.btnSnap.setText("Take image")

    def checkBoxMaxFPSHandler(self):
        if self.chkBoxMaxFPS.checkState():
            self.cameraThread.update_liveview = 99
        else:
            self.cameraThread.update_liveview = 1

    def btnSnapHandler(self):
        if self.recording:
            self.recording = False
            self.cameraThread.continuous_save = False
            self.btnSnap.setText("Record images")
            self.chkBoxRecord.setEnabled(True)
            self.chkBoxMaxFPS.setEnabled(True)
            end_time = perf_counter()
            start_time = self.cameraThread.start_time
            num_images = self.cameraThread.im_counter
            print(f"{num_images} images taken in {end_time - start_time:.2f}s ({num_images / (end_time-start_time):.2f} fps)")
            return

        # Set custom name
        custom_filename = '_' + self.txtBoxCustomFilename.text().replace(' ', '')
        self.cameraThread.custom_image_prefix = custom_filename if custom_filename != '_' else ''
        
        if self.chkBoxRecord.checkState():    
            self.cameraThread.continuous_save = True
            self.btnSnap.setText("Stop recording")
            self.recording = True
            self.chkBoxRecord.setEnabled(False)
            self.chkBoxMaxFPS.setEnabled(False)
            self.cameraThread.takeImage()
        else:
            self.cameraThread.single_save = True
            self.cameraThread.takeImage()

    def btnChangeBinningHandler(self):
        self.cameraThread.changeBinningMode()
        curr_binning_mode = self.cameraThread.livecam.camera.BinningHorizontal.GetValue()
        change_to = 1 if curr_binning_mode == 2 else 2
        self.btnChangeBinning.setText(f"Change to {change_to}X binning")

    @pyqtSlot(QImage)
    def updateImage(self, qimage):
        self.lblImage.setPixmap(QPixmap.fromImage(qimage))

    @pyqtSlot(int)
    def updateMotorPosition(self, val):
        self.vsFocus.setValue(val)
        self.txtBoxFocus.setText(f"{val}")

    @pyqtSlot(float)
    def updatePressureLabel(self, val):
        self.lblPressure.setText(f"{val:.2f} hPa")

    def updateFPS(self, val):
        self.lblFPS.setText(f"{val}fps")

    def vsLEDHandler(self):
        perc = int(self.vsLED.value())
        self.lblLED.setText(f"{perc}%")
        self.led.setDutyCycle(perc/100)

    def exposureSliderHandler(self):
        exposure = int(self.vsExposure.value())
        self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        self.txtBoxExposure.setText(f"{exposure}")

    def exposureTextBoxHandler(self):
        try:
            exposure = int(float(self.txtBoxExposure.text()))
            if exposure < MIN_EXPOSURE_US:
                raise
        except:
            print("Error parsing textbox exposure time input. Continuing...")
            self.txtBoxExposure.setText(f"{self.vsExposure.value()}")
            return
        try:
            self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        except:
            print("Invalid exposure, ignoring and continuing...")
            self.txtBoxExposure.setText(f"{self.vsExposure.value()}")
            return
        self.vsExposure.setValue(exposure)

    def btnFocusUpHandler(self):
        try:
            self.motor.move_rel(dir=Direction.CW, steps=1)
        except MotorControllerError as e:
            print(e)
            
        self.vsFocus.setValue(self.motor.pos)
        self.txtBoxFocus.setText(f"{self.motor.pos}")

    def btnFocusDownHandler(self):
        try:
            self.motor.move_rel(dir=Direction.CCW, steps=1)
        except MotorControllerError as e:
            print(e)

        self.vsFocus.setValue(self.motor.pos)
        self.txtBoxFocus.setText(f"{self.motor.pos}")

    def vsFocusHandler(self):
        pos = int(self.vsFocus.value())
        self.motor.move_abs(pos=pos)
        self.txtBoxFocus.setText(f"{self.motor.pos}")

    def focusTextBoxHandler(self):
        try:
            pos = int(float(self.txtBoxFocus.text()))
        except:
            print("Error parsing textbox focus position. Continuing...")
            self.txtBoxFocus.setText(f"{self.vsFocus.value()}")
            return

        try:
            self.motor.move_abs(pos)
        except:
            print("Invalid position to move the motor.")
            self.txtBoxFocus.setText(f"{self.vsFocus.value()}")
            return

        self.vsFocus.setValue(pos)

    def btnZStackHandler(self):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msgBox.setText("Press okay to sweep the motor and automatically find and move to the focal position.")
        msgBox.setWindowTitle("ZStack and Move to Focus")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        retval = msgBox.exec()

        if retval == QtWidgets.QMessageBox.Ok:
            self.vsFocus.blockSignals(True)
            self.txtBoxFocus.blockSignals(True)
            self.cameraThread.runZStack(self.motor)

    @pyqtSlot(int)
    def zStackFinished(self, val):
        self.vsFocus.blockSignals(False)
        self.txtBoxFocus.blockSignals(False)

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
            self.txtBoxFlow.setText(f"{self.vsFlow.value()}")
            return

        try:
            self.pressure_control.setDutyCycle(flow_duty_cycle)
        except:
            print("Invalid duty cycle, ignoring and continuing...")
            self.txtBoxFlow.setText(f"{self.vsFlow.value()}")
            return
        
        self.vsFlow.setValue(flow_duty_cycle)

    def manualFocusWithEncoder(self, increment: int):
        try:
            if increment == 1:
                self.motor.move_rel(dir=Direction.CW, steps=5)
            elif increment == -1:
                self.motor.move_rel(dir=Direction.CCW, steps=5)
            sleep(0.01)
            self.updateMotorPosition(self.motor.pos)
        except MotorControllerError:
            print("Invalid move.")
            self.encoder.setColor(255, 0, 0)
            sleep(0.1)
            self.encoder.setColor(12, 159, 217)


    def changeExposureWithEncoder(self, increment):
        if increment == 1:
            self.vsExposure.setValue(self.vsExposure.value() + 10)
        elif increment == -1:
            self.vsExposure.setValue(self.vsExposure.value() - 10)
        sleep(0.01)

    def exit(self):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msgBox.setText("Please remove the flow cell now. Only press okay after the flow cell has been removed. The syringe will move into the topmost position after pressing okay.")
        msgBox.setWindowTitle("Exit procedure")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        retval = msgBox.exec()

        if retval == QtWidgets.QMessageBox.Ok:
            # Move syringe back and de-energize
            self.pressure_control.close()
            # Turn off the LED
            self.led.close()
            # Turn off camera
            if self.cameraThread != None:
                self.cameraThread.camera_activated = False
            # Turn off encoder
            self.encoder.close()
            quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main_window = CameraStream()
    main_window.show()
    sys.exit(app.exec_())