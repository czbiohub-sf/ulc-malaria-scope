import sys
import csv
import traceback
import numpy as np

from transitions import Machine

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
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QImage, QPixmap, QIcon
from cv2 import imwrite
from qimage2ndarray import array2qimage

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ICON_PATH = "CZB-logo.png"
_FORM_PATH = "user_form.ui"
VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

# TODOs
## CLEAN UP NOTE??
## Use transitions for re-runs
## Clean up unnecessary imports

class ScopeOp(QObject):
    test = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.stop = False

    # @pyqtSlot(int)
    # def doSomethingWithInt(self, val):
    #     sleep(1)
    #     print(f"It's ya boi {val}")

    # def sayHi(self):
    #     print("Suh dude")
    #     # sleep(10)

class Acquisition(QThread):
    test = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.stop = False
    
    # def run(self):
    #     while not self.stop:
    #         self.test.emit(1)
    #         print("working")
    #         sleep(0.03)

class Oracle(Machine):

    def __init__(self, *args, **kwargs):

        # Instantiate experiment form window
        self.form_window = FormGUI()

        # Instantiate liveview window
        self.liveview_window = LiveviewGUI()

        # Instantiate scope operator and thread
        self.scopeOp = ScopeOp()
        self.scopeOpThread = QThread()
        self.scopeOp.moveToThread(self.scopeOpThread)

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisitionThread = QThread()
        self.acquisition.moveToThread(self.acquisitionThread)

        # Configure state machine
        states = [
            {'name' : 'standby', 'on_enter' : ['reset']},
            {'name' : 'precheck', 'on_enter' : ['start_precheck']},
            {'name' : 'form', 'on_enter' : ['open_form'], 'on_exit': ['close_form']},
            {'name' : 'setup', 'on_enter' : ['open_liveview', 'start_setup']},
            {'name' : 'run', 'on_enter': ['open_liveview', 'start_run']},
            # {'name' : 'survey', 'on_enter': ['open_survey']},
            ]
        Machine.__init__(self, states=states, queued=True, initial='standby')

        # TODO use conditions for re-running with experiment form (skip setup and precheck?)
        # self.add_transition(trigger='form2run', source='form', dest='run', before='open_liveview')
        self.add_transition(trigger='standby2precheck', source='standby', dest='precheck')
        self.add_transition(trigger='precheck2form', source='precheck', dest='form')
        self.add_transition(trigger='form2setup', source='form', dest='setup')
        self.add_transition(trigger='setup2run', source='setup', dest='run')
        self.add_transition(trigger='liveview2standby', source=['setup', 'run'], dest='standby', before='close_liveview')
        self.add_transition(trigger='end', source='*', dest='standby')

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.end)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.liveview2standby)

        self.standby2precheck()

    def start_precheck(self, *args):
        self.scope = MalariaScope()
        # TEMP for testing
        print(self.scope.get_component_status())
        if all(status==True for status in self.scope.get_component_status())
            self.precheck2form()
        else: 
            # TODOO print message here
            self.end()

    def start_setup(self, *args):
        # TBD run autopilot method here
        pass 

    def start_run(self, *args):
        # TBD run appropriate autopilot method here
        pass

    def open_form(self, *args):
        self.form_window.show()

    def save_form(self, *args):
        # TBD implement actual save here
        print(self.form_window.get_params())
        if valid:
            self.form2setup()
        else:
            # TODOO print message here
            # self.display_msg("Invalid form")
        # TODO VALIDATE FORM INPUTS HERE + APPEND DATE IF NEEDED

    def close_form(self, *args):
        self.form_window.close()

    def open_liveview(self, *args):
        self.liveview_window.show()

    def close_liveview(self, *args):
        self.liveview_window.close()
        # TBD pull up survey here

    def open_survey(self, *args):
        pass

    def reset(self, *args):
        # delete current scope?
        pass

    def display_message(self, icon, title, text, cancel=False, quit_after=False):
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

        if quit_after and msgBox.exec() == QMessageBox.Ok:
            quit()

        return msgBox.exec()

    # @pyqtSlot
    # def setupReceiveImg(self, img):
    #     self.autopilotThread.runSetup(img)
    #     # ^ includes autobrightness, autoflow control, autofocus
    #     self.livewindow.lblImg = img
    #     # ^ add FPS optimization

    # @pyqtSlot
    # def runReceiveImg(self, img):
    #     self.autopilotThread.runRun(img)
    #     # ^ includes autobrightness, autoflow control, autofocus
    #     self.livewindow.lblImg = img
    #     # ^ add FPS optimization

        
    # def startSetup(self, *args):
    #     # NOTE figure out why this call inputs an extra parameter
    #     print(*args)
    #     self.form_window.hide()
    #     print("TADA")
    #     self.acquisitionThread.img.connect(setupReceiveImg)

    #     # PSEUDOCODE
    #     self.liveview_window.show()
    #     self.acquisitionThread.start()

    #     print("TEMP setup tbd here")
    #     quit()

    # def startRun(self, *args):
    #     print(*args)
    #     self.acquisitionThread.img.disconnect(setupReceiveImg)
    #     self.acquisitionThread.img.connect(runReceiveImg)

    def exit(self):
        quit()
        
class FormGUI(QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        
        super(FormGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_FORM_PATH, self)
        self.setWindowIcon(QIcon(_ICON_PATH))

        # Set the focus order
        self.experiment_name.setFocus()
        self.setTabOrder(self.experiment_name, self.patient_id)
        self.setTabOrder(self.patient_id, self.flowcell_id)
        self.setTabOrder(self.flowcell_id, self.start_btn)

    def get_params(self) -> Dict:
        return {
            "experiment_name": self.experiment_name.text(),
            "patient_id": self.patient_id.text(),
            "flowcell_id": self.flowcell_id.text(),
        }
        
class LiveviewGUI(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(LiveviewGUI, self).__init__(*args, **kwargs)
        self._loadUI()
        
    def _loadUI(self):
        self.setWindowTitle('Malaria Scope')
        self.setGeometry(100, 100, 1100, 700)

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

if __name__ == "__main__":
    
    # def test():
    #     print("Start")
        
    #     i = 0
    #     while i < 3:
    #         # print(i)
    #         i += 1
    #         yield i
            
    #     return("Done")
        
    # t = test()
    # a = next(t)
    # print("OK" + str(a))
    # a = next(t)
    # print("OK" + str(a))
    # a = next(t)
    # print("OK" + str(a))
    # # next(t)
    # try:
    #     print(next(t))
    # except StopIteration as e:
    #     print(a)
    #     pass
    #     # print(e)
    # # next(t)

    app = QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec_())