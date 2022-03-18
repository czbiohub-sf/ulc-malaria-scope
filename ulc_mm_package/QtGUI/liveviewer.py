from ulc_mm_package.hardware.camera import CameraError, ULCMM_Camera
from ulc_mm_package.hardware.motorcontroller import DRV8825Nema, Direction, MotorControllerError, MotorInMotion
from ulc_mm_package.hardware.led_driver_tps54201ddct import LED_TPS5420TDDCT, LEDError
from ulc_mm_package.hardware.pim522_rotary_encoder import PIM522RotaryEncoder
from ulc_mm_package.hardware.pressure_control import PressureControl, PressureControlError
from ulc_mm_package.image_processing.zarrwriter import ZarrWriter

from ulc_mm_package.image_processing.zstack import takeZStackCoroutine, symmetricZStackCoroutine

import sys
import traceback
from time import perf_counter, sleep
from os import listdir, mkdir, path
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
EXTERNAL_DIR = "/media/pi/" + listdir("/media/pi/")[0] + "/"
WRITE_NUMPY = True

if BIG_SCREEN:
    _UI_FILE_DIR = "liveview_big.ui"
    LABEL_WIDTH = 1307
    LABEL_HEIGHT = 980
else:
    _UI_FILE_DIR = "liveview.ui"
    LABEL_WIDTH = 480
    LABEL_HEIGHT = 360

class AcquisitionThread(QThread):
    # Qt signals must be defined at the class-level (not instance-level)
    changePixmap = pyqtSignal(QImage)
    motorPosChanged = pyqtSignal(int)
    zStackFinished = pyqtSignal(int)
    updatePressure = pyqtSignal(float)
    fps = pyqtSignal(int)

    def __init__(self):
        super().__init__()
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
        self.custom_image_prefix = ''
        self.zarr_writer = ZarrWriter()
        self.pressure_sensor = None
        self.motor = None
        self.updateMotorPos = True
        self.start_time = perf_counter()

        try:
            self.camera = ULCMM_Camera()
            self.camera_activated = True
        except CameraError:
            self.camera_activated = False

    def run(self):
        while True:
            if self.camera_activated:
                try:
                    for image in self.camera.yieldImages():
                        self.updateGUIElements()
                        self.save(image)
                        self.zStack(image)

                        if self.liveview and self.update_counter % self.update_liveview == 0:
                            qimage = gray2qimage(image)
                            self.changePixmap.emit(qimage)
                except Exception as e:
                    # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                    # Once that happens, this can be swapped to catch the PyCameraException
                    print(e)
                    print(traceback.format_exc())

    def getMetaData(self):
        """Required metadata:
        - Measurement type (actual diagnostic experiment or data collection)
        - Sample type / sample name (i.e dataset name)
        - Motor position
        - Syringe position
        - Pressure reading
        - Ambient temperature (updated every N Frames)
        - RPi CPU temperature (updated every N frames)
        - Focus metric (updated every N frames)
        - LED power
        -
        """
        pass

    def save(self, image):
        if self.single_save:
            filename = path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + f"{self.custom_image_prefix}.tiff"
            cv2.imwrite(filename, image)
            self.single_save = False

        if self.continuous_save and self.continuous_dir_name != None:
            filename = path.join(self.main_dir, self.continuous_dir_name, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + f"{self.custom_image_prefix}_{self.im_counter:05}"
            if WRITE_NUMPY:
                np.save(filename+".npy", image)
            else:
                cv2.imwrite(filename+".tiff", image)
            self.im_counter += 1

    def updateGUIElements(self):
        self.update_counter += 1
        if self.updateMotorPos:
            self.motorPosChanged.emit(self.motor.pos)

        if self.update_counter % self.num_loops == 0:
            self.update_counter = 0
            if self.pressure_sensor != None:
                self.updatePressure.emit(self.pressure_sensor.pressure)
            self.fps.emit(int(self.num_loops / (perf_counter() - self.start_time)))
            self.start_time = perf_counter()

    def updateExposure(self, exposure):
        self.camera.exposureTime_ms = exposure

    def takeImage(self):
        if self.main_dir == None:
            self.main_dir = EXTERNAL_DIR + datetime.now().strftime("%Y-%m-%d-%H%M%S")
            mkdir(self.main_dir)

        if self.continuous_save:
            self.continuous_dir_name = datetime.now().strftime("%Y-%m-%d-%H%M%S") + f"{self.custom_image_prefix}"
            mkdir(path.join(self.main_dir, self.continuous_dir_name))
            self.fps_timer = perf_counter()
            self.im_counter = 0

    def changeBinningMode(self):
        if self.camera_activated:
            self.camera.stopAcquisition()
            self.camera_activated = False
        
        if self.camera.camera.BinningHorizontal.GetValue() == 2:
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
        self.zstack = takeZStackCoroutine(None, motor, save_loc=EXTERNAL_DIR)
        self.zstack.send(None)

    def runLocalZStack(self, motor: DRV8825Nema, start_point: int):
        self.takeZStack = True
        self.motor = motor
        self.zstack = symmetricZStackCoroutine(None, motor, start_point, save_loc=EXTERNAL_DIR)
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

class MalariaScopeGUI(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)
        
        # List hardware components
        self.acquisitionThread = None
        self.motor = None
        self.pressure_control = None
        self.encoder = PIM522RotaryEncoder(self.manualFocusWithEncoder)
        self.led = None

        # Load the ui file 
        uic.loadUi(_UI_FILE_DIR, self)

        # Start the video stream
        self.acquisitionThread = AcquisitionThread()
        self.recording = False
        
        if not self.acquisitionThread.camera_activated:
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
            self.vsFocus.valueChanged.connect(self.vsFocusValueChangedHandler)
            self.vsFocus.sliderReleased.connect(self.vsFocusSliderReleasedHandler)
            self.vsFocus.sliderPressed.connect(self.vsFocusClickHandler)
            self.txtBoxFocus.editingFinished.connect(self.focusTextBoxHandler)
            self.txtBoxFocus.gotFocus.connect(self.txtBoxFocusGotFocus)
            self.btnFullZStack.clicked.connect(self.btnFullZStackHandler)
            self.btnLocalZStack.clicked.connect(self.btnLocalZStackHandler)
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
        self.acquisitionThread.changePixmap.connect(self.updateImage)
        self.acquisitionThread.motorPosChanged.connect(self.updateMotorPosition)
        self.acquisitionThread.motor = self.motor
        self.acquisitionThread.zStackFinished.connect(self.enableMotorUIElements)
        self.acquisitionThread.updatePressure.connect(self.updatePressureLabel)
        self.acquisitionThread.fps.connect(self.updateFPS)
        self.acquisitionThread.pressure_sensor = self.pressure_control.mpr
        self.txtBoxExposure.editingFinished.connect(self.exposureTextBoxHandler)
        self.chkBoxRecord.stateChanged.connect(self.checkBoxRecordHandler)
        self.chkBoxMaxFPS.stateChanged.connect(self.checkBoxMaxFPSHandler)
        self.btnSnap.clicked.connect(self.btnSnapHandler)
        self.vsExposure.valueChanged.connect(self.exposureSliderHandler)
        self.btnChangeBinning.clicked.connect(self.btnChangeBinningHandler)
        self.acquisitionThread.start()

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

    def txtBoxFocusGotFocus(self):
        self.acquisitionThread.updateMotorPos = False

    def vsFocusClickHandler(self):
        self.acquisitionThread.updateMotorPos = False
        
    def checkBoxRecordHandler(self):
        if self.chkBoxRecord.checkState():
            # Continuously record images to a new subfolder
            self.btnSnap.setText("Record images")
        else:
            self.btnSnap.setText("Take image")

    def checkBoxMaxFPSHandler(self):
        if self.chkBoxMaxFPS.checkState():
            self.acquisitionThread.update_liveview = 99
        else:
            self.acquisitionThread.update_liveview = 1

    def btnSnapHandler(self):
        if self.recording:
            self.recording = False
            self.acquisitionThread.continuous_save = False
            self.btnSnap.setText("Record images")
            self.chkBoxRecord.setEnabled(True)
            self.chkBoxMaxFPS.setEnabled(True)
            end_time = perf_counter()
            start_time = self.acquisitionThread.fps_timer
            num_images = self.acquisitionThread.im_counter
            print(f"{num_images} images taken in {end_time - start_time:.2f}s ({num_images / (end_time-start_time):.2f} fps)")
            return

        # Set custom name
        custom_filename = '_' + self.txtBoxCustomFilename.text().replace(' ', '')
        self.acquisitionThread.custom_image_prefix = custom_filename if custom_filename != '_' else ''
        
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
        curr_binning_mode = self.acquisitionThread.camera.camera.BinningHorizontal.GetValue()
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
        self.acquisitionThread.updateExposure(exposure / 1000) # Exposure time us -> ms
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
            self.acquisitionThread.updateExposure(exposure / 1000) # Exposure time us -> ms
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

    def vsFocusValueChangedHandler(self):
        pos = int(self.vsFocus.value())
        self.txtBoxFocus.setText(f"{pos}")

    def vsFocusSliderReleasedHandler(self):
        pos = int(self.vsFocus.value())
        try:
            self.motor.threaded_move_abs(pos=pos)
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
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msgBox.setText("Press okay to sweep the motor over its entire range and automatically find and move to the focal position.")
        msgBox.setWindowTitle("Full Range ZStack")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        retval = msgBox.exec()

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runFullZStack(self.motor)

    def btnLocalZStackHandler(self):
        msgBox = QtWidgets.QMessageBox()
        msgBox.setIcon(QtWidgets.QMessageBox.Icon.Information)
        msgBox.setText("Press okay to sweep the motor over its current nearby vicinity and move to the focal position.")
        msgBox.setWindowTitle("Local Vicinity ZStack")
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        retval = msgBox.exec()

        if retval == QtWidgets.QMessageBox.Ok:
            self.disableMotorUIElements()
            self.acquisitionThread.runLocalZStack(self.motor, self.motor.pos)

    def disableMotorUIElements(self):
        self.vsFocus.blockSignals(True)
        self.txtBoxFocus.blockSignals(True)
        self.btnFocusUp.setEnabled(False)
        self.btnFocusDown.setEnabled(False)
        self.btnLocalZStack.setEnabled(False)
        self.btnFullZStack.setEnabled(False)
    
    @pyqtSlot(int)
    def enableMotorUIElements(self, _):
        self.btnFocusUp.setEnabled(True)
        self.btnFocusDown.setEnabled(True)
        self.btnLocalZStack.setEnabled(True)
        self.btnFullZStack.setEnabled(True)
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
                self.motor.threaded_move_rel(dir=Direction.CW, steps=1)
            elif increment == -1:
                self.motor.threaded_move_rel(dir=Direction.CCW, steps=1)
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
            if self.acquisitionThread != None:
                self.acquisitionThread.camera_activated = False
            # Turn off encoder
            self.encoder.close()
            quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main_window = MalariaScopeGUI()
    main_window.show()
    sys.exit(app.exec_())