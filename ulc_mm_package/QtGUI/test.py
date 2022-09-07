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
    QLineEdit, QComboBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QImage, QPixmap, QIcon
from cv2 import imwrite
from qimage2ndarray import array2qimage

from ulc_mm_package.hardware.scope import MalariaScope

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ICON_PATH = "CZB-logo.png"
_FORM_PATH = "user_form.ui"
VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

# TODOs
## CLEAN UP NOTE??
## Use transitions for re-runs
## Clean up unnecessary imports
## Replace all exit() with end() and go back to pre-experiment dialog

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
        self.mscope = MalariaScope()
        component_status = self.mscope.get_component_status()
        # TEMP for testing
        if True:
        # if all([status==True for status in component_status.values()]):
            self.precheck2form()
        else: 
            failed_components = [comp.name for comp in component_status if component_status.get(comp)==False]
            _ = self._display_message(
                QMessageBox.Icon.Critical,
                "Hardware pre-check failed",
                "The following component(s) could not be instantiated: {}"
                    .format((",".join(failed_components)).capitalize()),
                exit_after=True,
                )
            print("Escaped")

    def start_setup(self, *args):
        # TBD run autopilot method here
        pass 

    def start_run(self, *args):
        # TBD run appropriate autopilot method here
        pass

    def open_form(self, *args):
        self.form_window.show()

    def save_form(self, *args):

        # TEMP delete this print
        print(self.form_window.get_form_input())
        try:
            # TBD implement actual save here
            # TODO build input validation into get_form_input()
            # self.mscope.data_storage.createNewExperiment(self.form_window.get_form_input())
            pass
        # TODO target correct exception here
        except Exception as e:
            _ = self._display_message(
                QMessageBox.Icon.Warning,
                "Invalid form input",
                "The following entries are invalid:",   # Add proper warnings here
                exit_after=True,
                )

        self.form2setup()

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

    def _display_message(self, icon, title, text, cancel=False, exit_after=False):
        msgBox = QMessageBox()
        msgBox.setWindowIcon(QIcon(_ICON_PATH))
        msgBox.setIcon(icon)
        msgBox.setWindowTitle(f"{title}")
        msgBox.setText(f"{text}")

        if cancel:
            msgBox.setStandardButtons(
                QMessageBox.Ok | QMessageBox.Cancel
            )
        else:
            msgBox.setStandardButtons(QMessageBox.Ok)

        if exit_after and msgBox.exec() == QMessageBox.Ok:
            self.exit()

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
        print("Exiting program")
        quit()
        
class FormGUI(QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        
        super(FormGUI, self).__init__(*args, **kwargs)
        self._load_ui()

    def _load_ui(self):
        self.setWindowTitle('Experiment form')
        self.setGeometry(0, 0, 675, 500)
        self.setWindowIcon(QIcon(_ICON_PATH))

        # Set up layout + widget
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        # Labels
        self.operator_id_lbl = QLabel("Operator ID")
        self.patient_id_lbl = QLabel("Patient ID")
        self.flowcell_id_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Comments")
        self.protocol_lbl = QLabel("Protocol")
        self.site_lbl = QLabel("Site")

        # Text boxes
        self.operator_id = QLineEdit()
        self.patient_id = QLineEdit()
        self.flowcell_id = QLineEdit()
        self.notes = QLineEdit()

        # Buttons
        self.exit_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.protocol = QComboBox()
        self.site = QComboBox()

        # Configure widgets
        # notes_size_policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # notes_size_policy.setVerticalStretch(1)
        # self.notes.setSizePolicy(notes_size_policy)

        self.protocol.addItems(["Default"])
        self.site.addItems(["Tororo, Uganda"])

        # Place widgets
        self.main_layout.addWidget(self.operator_id_lbl, 0, 0)
        self.main_layout.addWidget(self.patient_id_lbl, 1, 0)
        self.main_layout.addWidget(self.flowcell_id_lbl, 2, 0)
        self.main_layout.addWidget(self.protocol_lbl, 3, 0)
        self.main_layout.addWidget(self.site_lbl, 4, 0)
        self.main_layout.addWidget(self.notes_lbl, 5, 0)
        self.main_layout.addWidget(self.exit_btn, 6, 0)

        self.main_layout.addWidget(self.operator_id, 0, 1)
        self.main_layout.addWidget(self.patient_id, 1, 1)
        self.main_layout.addWidget(self.flowcell_id, 2, 1)
        self.main_layout.addWidget(self.protocol, 3, 1)
        self.main_layout.addWidget(self.site, 4, 1)
        self.main_layout.addWidget(self.notes, 5, 1)
        self.main_layout.addWidget(self.start_btn, 6, 1)

        # Set the focus order
        self.operator_id.setFocus()
        # self.setTabOrder(self.operator_id, self.patient_id)
        # self.setTabOrder(self.patient_id, self.flowcell_id)
        # self.setTabOrder(self.flowcell_id, self.protocol)
        # self.setTabOrder(self.protocol, self.site)
        # self.setTabOrder(self.site, self.notes)
        self.setTabOrder(self.notes, self.start_btn)

    def get_form_input(self) -> Dict:
        return {
            "operator_id": self.operator_id.text(),
            "patient_id": self.patient_id.text(),
            "flowcell_id": self.flowcell_id.text(),
            "protocol": self.protocol.currentText(),
            "site": self.site.currentText(),
            "notes": self.notes.text(),
        }
        
class LiveviewGUI(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(LiveviewGUI, self).__init__(*args, **kwargs)
        self._load_ui()
        
    def _load_ui(self):
        self.setWindowTitle('Malaria scope')
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