from ulc_mm_package.hardware.camera import LiveCamera

import sys
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QCoreApplication, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

_UI_FILE_DIR = "liveview.ui"
LABEL_WIDTH = 325
LABEL_HEIGHT = 260

class CameraThread(QThread):
    changePixmap = pyqtSignal(QImage)
    # Create and start the camera
    try:
        livecam = LiveCamera()
    except Exception as e:
        print(f"Could not create the Basler camera:\n{e}")

    def run(self):
        while True:
            try:
                for image in self.livecam.yieldImages():
                    h, w = image.shape
                    qimage = QImage(image, w, h, QImage.Format_Grayscale8)
                    qimage = qimage.scaled(LABEL_WIDTH, LABEL_HEIGHT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.changePixmap.emit(qimage)
            except Exception as e:
                # TODO - think about error modes and how to deal with them
                print(e)


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

    @pyqtSlot(QImage)
    def updateImage(self, image):
        self.lblImage.setPixmap(QPixmap.fromImage(image))

def main():
    app = QtWidgets.QApplication(sys.argv)
    main = CameraStream()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()