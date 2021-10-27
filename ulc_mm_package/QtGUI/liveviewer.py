from re import S
from ulc_mm_package.hardware.camera import ULCMM_Camera
from ulc_mm_package.hardware.motorcontroller import DRV88258Nema
from ulc_mm_package.hardware.zarrwriter import ZarrWriter

import sys
import traceback
from os import path, mkdir
from datetime import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
from cv2 import imwrite

_UI_FILE_DIR = "liveview.ui"
LABEL_WIDTH = 480
LABEL_HEIGHT = 360

class CameraThread(QThread):
    changePixmap = pyqtSignal(QImage)
    main_dir = None
    single_save = False
    continuous_save = False

    try:
        livecam = ULCMM_Camera()
        livecam.print()
    except Exception as e:
        print(f"Could not create the Basler camera:\n{e}. Closing application...")
        exit()

    def run(self):
        while True:
            try:
                for image in self.livecam.yieldImages():
                    self.image = image

                    if self.single_save:
                        filename = path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + ".jpeg"
                        imwrite(filename, image)
                        self.single_save = False

                    if self.continuous_save:
                        filename = path.join(self.main_dir, self.continuous_dir_name, datetime.now().strftime("%Y-%m-%d-%H%M%S")) + ".jpeg"
                        imwrite(filename, image)
                    
                    h, w = image.shape
                    qimage = QImage(image, w, h, QImage.Format_Grayscale8)
                    qimage = qimage.scaled(LABEL_WIDTH, LABEL_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.changePixmap.emit(qimage)
            except Exception as e:
                print(e)
                print(traceback.format_exc())

    def updateExposure(self, exposure):
        self.livecam.exposureTime_ms = exposure

    def takeImage(self):
        if self.main_dir == None:
            self.main_dir = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            mkdir(self.main_dir)
            print(self.main_dir)

        if self.continuous_save:
            self.continuous_dir_name = datetime.now().strftime("%Y-%m-%d-%H%M%S")
            mkdir(path.join(self.main_dir, self.continuous_dir_name))

    
        
class CameraStream(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(CameraStream, self).__init__(*args, **kwargs)

        # Load the ui file 
        uic.loadUi(_UI_FILE_DIR, self)

        self.showFullScreen()

        # Start the video stream
        self.cameraThread = CameraThread()
        self.cameraThread.changePixmap.connect(self.updateImage)
        self.cameraThread.start()
        self.recording = False

        # # Create motor w/ default pins/settings (full step)
        # self.motor = DRV88258Nema()
        # self.motor.homeToLimitSwitches()

        # Connect UI elements to actions
        self.vsExposure.valueChanged.connect(self.updateExposureSlider)
        self.txtBoxExposure.textChanged.connect(self.updateExposureTextBox)
        self.chkBoxRecord.stateChanged.connect(self.checkBoxHandler)
        self.btnSnap.clicked.connect(self.takeImage)
        
        self.btnFlowUp.clicked.connect(self.increaseFlowPWM)
        self.btnFlowDown.clicked.connect(self.decreaseFlowPWM)
        self.txtBoxFlow.textChanged.connect(self.setFlowPWM)

    def checkBoxHandler(self):
        if self.chkBoxRecord.checkState():
            # Continuously record images to a new subfolder
            self.btnSnap.setText("Record images")
        else:
            self.btnSnap.setText("Take image")
        

    def takeImage(self):
        if self.recording:
            self.recording = False
            self.btnSnap.setText("Record images")
            self.chkBoxRecord.setEnabled(True)
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

    def updateExposureSlider(self):
        exposure = int(self.vsExposure.value())
        self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        self.lblExposure.setText(f"Exposure: {exposure} us")
        self.txtBoxExposure.setText(f"{exposure}")

    def updateExposureTextBox(self):
        try:
            exposure = int(self.txtBoxExposure.text())
        except:
            print("Error parsing textbox exposure time input. Continuing...")
            return
        try:
            self.cameraThread.updateExposure(exposure / 1000) # Exposure time us -> ms
        except:
            return
        self.lblExposure.setText(f"Exposure: {exposure} us")
        self.vsExposure.setValue(exposure)

    def increaseFlowPWM(self):
        pass

    def decreaseFlowPWM(self):
        pass

    def setFlowPWM(self):
        try:
            flow_pwm = int(self.txtBoxFlow.text())
        except:
            print("Error parsing textbox flow PWM input. Continuing...")
            return

        
        pass

def main():
    app = QtWidgets.QApplication(sys.argv)
    main = CameraStream()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()