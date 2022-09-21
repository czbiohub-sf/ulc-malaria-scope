import sys
import traceback
from xml.sax.handler import property_declaration_handler
import numpy as np

from transitions import Machine, State
from typing import Dict
from time import perf_counter, sleep
from qimage2ndarray import gray2qimage

from PyQt5.QtWidgets import (
    QApplication, QMainWindow,
    QDialog, QMessageBox,
    QGridLayout, QVBoxLayout, QHBoxLayout,
    QSizePolicy,
    QWidget, QTabWidget,   
    QLabel, QPushButton, QLineEdit, QComboBox,
)
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QIcon

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *


QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ICON_PATH = "CZB-logo.png"
_FORM_PATH = "user_form.ui"
_VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

# TODOs
## CLEAN UP NOTE??
## Clean up imports

# NICE TO HAVE
# define types for arg inputs and Nonetype variables
## Validate experiment form inputs

# SHUTOFF
## Replace all exit() with end() and go back to pre-experiment dialog
# deal with camera shutoff
# thread termination?
        # self.thread.started.connect(self.worker.run)
        # self.worker.finished.connect(self.thread.quit)
        # self.worker.finished.connect(self.worker.deleteLater)
        # self.thread.finished.connect(self.thread.deleteLater)
        # self.worker.progress.connect(self.reportProgress)

# Implement proper shutoff
# FPS handling < and ^ may be better handled by timer? 

# Implement correct setup order after merging
# Populate info panel
# Implement survey and metadata feed 
# Implement exception handling for camera

class ScopeOpState(State):

    def __init__(self, name, on_enter=None, on_exit=None, 
                ignore_invalid_triggers=None, 
                autoconnect=False, signal=None, slot=None):

        # Autoconnect connects signals/slots after "on_enter" functions, and disconnects before "on_exit" functions
        if autoconnect:
            if signal == None or slot == None:
                raise ValueError('Autoconnect is enabled for state "{}" but signal and/or slot specification is missing.'.format(name))

            if on_enter == None:
                on_enter = self._connect
            else:
                on_enter.append(self._connect)
        
            if on_exit == None:
                on_exit = self._disconnect
            else:
                on_exit.insert(0, self._disconnect)

        self.signal = signal
        self.slot = slot

        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers)

    def _connect(self):
        self.signal.connect(self.slot)

    def _disconnect(self):
        self.signal.disconnect(self.slot)
        
class ScopeOp(QObject, Machine):
    precheck_done = pyqtSignal()
    freeze_liveview = pyqtSignal(bool)

    state_cls = ScopeOpState

    def __init__(self, img_signal):
        super().__init__()
        self.mscope = MalariaScope()
        self.img_signal = img_signal

        self.final_brightness = None
        self.final_fbounds = None

        states = [
            {'name' : 'standby'},
            {'name' : 'autobrightness', 
                'on_enter' : [self._start_autobrightness],
                'autoconnect' : True, 
                'signal' : self.img_signal, 
                'slot' : self.run_autobrightness,
                },
            {'name' : 'fbounds', 
                'on_enter' : [self._start_fbounds],
                'autoconnect' : True, 
                'signal' : self.img_signal, 
                'slot' : self.run_fbounds,
                },
            {'name' : 'experiment', 
                'autoconnect' : True, 
                'signal' : self.img_signal, 
                'slot' : self.run_experiment,
                },
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='end', source='*', dest='standby')

    def precheck(self):
        component_status = self.mscope.get_component_status()
        print(component_status)

        # TEMP for testing
        if True:
        # if all([status==True for status in component_status.values()]):
            self.precheck_done.emit()
            print("Passed precheck")
        else: 
            failed_components = [comp.name for comp in component_status if component_status.get(comp)==False]
            _ = self._display_message(
                QMessageBox.Icon.Critical,
                "Hardware pre-check failed",
                "The following component(s) could not be instantiated: {}"
                    .format((",".join(failed_components)).capitalize()),
                exit_after=True,
                )
            print("Failed precheck")

    def start_setup(self):
        self.to_standby()
        self.next_state()

    def _start_autobrightness(self):
        self.autobrightness_routine = autobrightnessCoroutine(self.mscope)
        self.autobrightness_routine.send(None)

        self.freeze_liveview.emit(False)

    def _start_fbounds(self):
        self.fbounds_routine = getFocusBoundsCoroutine(self.mscope)
        self.fbounds_routine.send(None)

        self.freeze_liveview.emit(False)

    @pyqtSlot(np.ndarray)
    def run_autobrightness(self, img):
        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.final_brightness = e.value
            print(self.final_brightness)
            self.next_state()

    @pyqtSlot(np.ndarray)
    def run_fbounds(self, img):
        try:
            self.fbounds_routine.send(img)
        except StopIteration as e:
            self.final_fbounds = e.value
            print(self.final_fbounds)
            self.next_state()

    @pyqtSlot(np.ndarray)
    def run_experiment(self, img):
        print("Running experiment")


class Acquisition(QObject):
    new_img = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()
        self.mscope = None

    def get_mscope(self, mscope):
        self.mscope = mscope

    def run(self):
        # # TODO is there a better way to use this
        # while True:
        try:
            for image in self.mscope.camera.yieldImages():
                self.new_img.emit(image) 
        except Exception as e:
            # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
            # Once that happens, this can be swapped to catch the PyCameraException
            print(e)
            print(traceback.format_exc())

    @pyqtSlot(np.ndarray)
    def update_img(self, img):
        self.liveview_img.setPixmap(QPixmap.fromImage(gray2qimage(img)))
            
class Oracle(Machine):

    def __init__(self, *args, **kwargs):
        # Instantiate windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)
        self.acquisition_thread.started.connect(self.acquisition.run)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp(self.acquisition.new_img)
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Configure state machine
        states = [
            {'name' : 'standby'},
            {'name' : 'precheck', 
                'on_enter' : [self._start_precheck]},
            {'name' : 'form', 
                'on_enter' : [lambda *args : self.form_window.show()], 
                'on_exit' : [lambda *args : self.form_window.close()]},
            {'name' : 'liveview', 
                'on_enter' : [lambda *args : self.liveview_window.show(), self._start_liveview], 
                'on_exit' : [self._end_liveview, lambda *args : self.liveview_window.close()]},
            # {'name' : 'survey', 'on_enter' : ['open_survey']},
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='reset', source='*', dest='standby', after='_reset')

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self._save_form)
        self.form_window.exit_btn.clicked.connect(self.end)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.end)

        # Connect scopeop signals and slots
        self.scopeop.precheck_done.connect(self.next_state)
        self.scopeop.freeze_liveview.connect(self._freeze_liveview)

        # Trigger first transition
        self.to_precheck()

    def _freeze_liveview(self, freeze):
        if freeze:
            self.acquisition.new_img.disconnect(self.liveview_window.update_img)
        else:            
            self.acquisition.new_img.connect(self.liveview_window.update_img)

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
            self.end()

        return msgBox.exec()

    def _reset(self, *args):
        pass
        # delete current scope?

    def _start_precheck(self, *args):
        self.scopeop.precheck()
        self.acquisition.get_mscope(self.scopeop.mscope)

    def _save_form(self, *args):
        try:
            # TBD implement actual save here
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

        self.next_state()

    def _start_liveview(self, *args):
        self.acquisition.new_img.connect(self.liveview_window.update_img)
        self.acquisition_thread.start()

        self.scopeop.start_setup()

    def _end_liveview(self, *args):
        self.scopeop.to_standby()
        self.acquisition.new_img.disconnect(self.liveview_window.update_img)

    def end(self, *args):
        self.acquisition_thread.quit()
        self.scopeop_thread.quit()
        print("Exiting program")
        # quit()
        
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
        self.fps_scale = 2

    @pyqtSlot(np.ndarray)
    def update_img(self, img):
        # if self.fps % self.fps_scale == 0:
        self.liveview_img.setPixmap(QPixmap.fromImage(gray2qimage(img)))

    def set_fps_scale(self, fps_scale):
        self.fps_scale = fps_scale
        
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

    app = QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec_())