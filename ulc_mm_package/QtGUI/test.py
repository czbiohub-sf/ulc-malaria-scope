import sys
import csv
from tkinter import N
import traceback
import numpy as np
import enum

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
from ulc_mm_package.hardware.scope_routines import *

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
### Implement survey?
### Test with basic mockup coroutines?

class ScopeOp(QObject):
    setup_done = pyqtSignal()

    def __init__(self, MalariaScope : mscope):
        super().__init__()
        self.mscope = mscope
        self.state = ScopeOpStates.AUTOBRIGHTNESS

        self.final_brightness = None
        self.final_focus_bounds = None

    def start_setup(self, img):
        self.autobrightness_routine = autobrightnessCoroutine(self.mscope)
        self.focus_bounds_routine = getFocusBoundsCoroutine(self.mscope)
        self.autofocus_routine = focusCoroutine(self.mscope)

        self.setup_routines = [ 
            self.autobrightness_routine,
            self.focus_bounds_routine,
            self.autofocus_routine,
            self.run,
            ]
        self.img_processer = self.setup_routines.pop(0)

    def run(self, img):
        print("I'm running")

    @pyqtSlot(QImage)
    def img_handler(self, img):
        try:
            self.img_processer(img)
        except StopIteration as e:
            self.img_processer = self.setup_routines.pop(0)
            if len(self.setup_routines) == 0:
                self.setup_done.emit()

class Acquisition(QObject):
    update_img = pyqtSignal(int)

    def __init__(self):
        super().__init__()

    def run(self):
        while True:
            if self.camera_activated:
                try:
                    for image in self.camera.yieldImages():
                        qimage = gray2qimage(image)
                        self.update_img.emit(qimage)
                except Exception as e:
                    # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
                    # Once that happens, this can be swapped to catch the PyCameraException
                    print(e)
                    print(traceback.format_exc())

class Oracle(Machine):

    def __init__(self, *args, **kwargs):

        # Instantiate experiment form window
        self.form_window = FormGUI()

        # Instantiate liveview window
        self.liveview_window = LiveviewGUI()

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp()
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)

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

        # Connect signals and slots
        self.acquisition.update_img.connect(self.liveview_window.update_img)
        self.acquisition.update_img.connect(self.scopeop.img_handler)

        # Trigger first transition
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
        self.ScopeOp.start_setup()

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
        self.participant_id_lbl = QLabel("Participant ID")
        self.flowcell_id_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Comments")
        self.protocol_lbl = QLabel("Protocol")
        self.site_lbl = QLabel("Site")

        # Text boxes
        self.operator_id = QLineEdit()
        self.participant_id = QLineEdit()
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
        self.main_layout.addWidget(self.participant_id_lbl, 1, 0)
        self.main_layout.addWidget(self.flowcell_id_lbl, 2, 0)
        self.main_layout.addWidget(self.protocol_lbl, 3, 0)
        self.main_layout.addWidget(self.site_lbl, 4, 0)
        self.main_layout.addWidget(self.notes_lbl, 5, 0)
        self.main_layout.addWidget(self.exit_btn, 6, 0)

        self.main_layout.addWidget(self.operator_id, 0, 1)
        self.main_layout.addWidget(self.participant_id, 1, 1)
        self.main_layout.addWidget(self.flowcell_id, 2, 1)
        self.main_layout.addWidget(self.protocol, 3, 1)
        self.main_layout.addWidget(self.site, 4, 1)
        self.main_layout.addWidget(self.notes, 5, 1)
        self.main_layout.addWidget(self.start_btn, 6, 1)

        # Set the focus order
        self.operator_id.setFocus()
        # self.setTabOrder(self.operator_id, self.participant_id)
        # self.setTabOrder(self.participant_id, self.flowcell_id)
        # self.setTabOrder(self.flowcell_id, self.protocol)
        # self.setTabOrder(self.protocol, self.site)
        # self.setTabOrder(self.site, self.notes)
        self.setTabOrder(self.notes, self.start_btn)

    def get_form_input(self) -> Dict:
        return {
            "operator_id": self.operator_id.text(),
            "participant_id": self.participant_id.text(),
            "flowcell_id": self.flowcell_id.text(),
            "protocol": self.protocol.currentText(),
            "site": self.site.currentText(),
            "notes": self.notes.text(),
        }
        
class LiveviewGUI(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(LiveviewGUI, self).__init__(*args, **kwargs)
        self._load_ui()

    @pyqtSlot(QImage)
    def update_img(self, qimage):
        self.liveview_img.setPixmap(QPixmap.fromImage(qimage))
        # TODO add FPS handling
        
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
    
    def test():
        print("Start")
        
        i = 0
        while i < 3:
            # print(i)
            i += 1
            yield i
            
        return("Done")
        
    t = test()
    a = next(t)
    print("OK" + str(a))
    a = next(t)
    print("OK" + str(a))
    a = next(t)
    print("OK" + str(a))
    next(t)
    try:
        print(next(t))
    except StopIteration as e:
        print(a)
        pass
        # print(e)
    # next(t)

    # app = QApplication(sys.argv)
    # oracle = Oracle()
    # sys.exit(app.exec_())