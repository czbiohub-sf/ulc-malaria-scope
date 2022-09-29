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
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QImage, QPixmap, QIcon

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *

from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS, PER_IMAGE_METADATA_KEYS, TARGET_FLOWRATE

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ICON_PATH = "CZB-logo.png"
_FORM_PATH = "user_form.ui"
_VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

_UPDATE_PERIOD = 30

# Move QTimer to correct spot
# Check 4036 notes

# TODOs
# TH sensor needs to be simulated too
## CLEAN UP NOTE??
## Clean up imports

# NICE TO HAVE
# Use "on_exception" to trigger exception handler
# define types for arg inputs and Nonetype variables
## Validate experiment form inputs
# Implement exception handling for camera

# SHUTOFF
## Replace all exit() with end() and go back to pre-experiment dialog
# deal with camera shutoff

# on_enter and on_exit order doesnt work
# Implement proper shutoff
# FPS handling < and ^ may be better handled by timer? 

# Populate info panel
# Implement survey and metadata feed 

class ScopeOpState(State):

    def __init__(self, name, on_enter=None, on_exit=None, ignore_invalid_triggers=None,
                signal=None, slot=None):

        self.signal = signal
        self.slot = slot

        if self.signal == None or self.slot == None:
            if (not self.signal == None) or (not self.slot == None):
                raise ValueError(f'Signal and/or slot specification is missing for state {name}.')

        # Connect signals/slots after "on_enter" events, and disconnect before "on_exit"
        else:
            if on_enter == None:
                on_enter = self._connect
            else:
                on_enter.append(self._connect)
        
            if on_exit == None:
                on_exit = self._disconnect
            else:
                on_exit.insert(0, self._disconnect)

        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers)

    def _connect(self):
        self.signal.connect(self.slot, type=Qt.BlockingQueuedConnection)

    def _disconnect(self):
        print("disconnecting " + self.name)
        self.signal.disconnect(self.slot)

        
class ScopeOp(QObject, Machine):
    precheck_done = pyqtSignal()
    freeze_liveview = pyqtSignal(bool)
    error = pyqtSignal()

    state_cls = ScopeOpState

    def __init__(self, img_signal):
        super().__init__()
        self.mscope = MalariaScope()
        self.img_signal = img_signal

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None

        states = [
            {'name' : 'standby',
                'on_enter' : [self._reset]},
            {'name' : 'autobrightness', 
                'on_enter' : [self._start_autobrightness],
                'signal' : self.img_signal, 
                'slot' : self.run_autobrightness,
                },
            {'name' : 'cellfinder', 
                'on_enter' : [self._start_cellfinder, self._freeze_liveview],
                'on_exit' : [self._unfreeze_liveview],
                'signal' : self.img_signal, 
                'slot' : self.run_cellfinder,
                },
            {'name' : 'SSAF', 
                'on_enter' : [self._start_SSAF],
                'signal' : self.img_signal, 
                'slot' : self.run_SSAF,
                },
            {'name' : 'fastflow', 
                'on_enter' : [self._start_fastflow],
                'signal' : self.img_signal, 
                'slot' : self.run_fastflow,
                },
            {'name' : 'experiment', 
                'on_enter' : [self._start_experiment],
                'signal' : self.img_signal, 
                'slot' : self.run_experiment,
                },
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='end', source='*', dest='standby')

    def precheck(self):
        component_status = self.mscope.getComponentStatus()
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

    def start(self):
        print("Starting experiment")

        self.to_standby()
        self.next_state()

    def _reset(self):
        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def _start_autobrightness(self):
        self.autobrightness_routine = autobrightnessRoutine(self.mscope)
        self.autobrightness_routine.send(None)

    def _start_cellfinder(self):        
        self.cellfinder_routine = find_cells_routine(self.mscope)
        self.cellfinder_routine.send(None)

    def _start_SSAF(self):
        print(f"Moving motor to {self.cellfinder_result}")
        self.mscope.motor.move_abs(self.cellfinder_result)

        self.SSAF_routine = singleShotAutofocusRoutine(self.mscope, None)
        self.SSAF_routine.send(None)

    def _start_fastflow(self):
        self.fastflow_routine = fastFlowRoutine(self.mscope, None)
        self.fastflow_routine.send(None)

    def _start_experiment(self):
        self.PSSAF_routine = periodicAutofocusWrapper(mscope, None)
        self.flowcontrol_routine = flowControlRoutine(mscope, TARGET_FLOWRATE, None)

    @pyqtSlot(np.ndarray)
    def run_autobrightness(self, img):
        if self.autobrightness_result == None:
            try:
                self.autobrightness_routine.send(img)
            except StopIteration as e:
                self.autobrightness_result = e.value
                print(f"Mean pixel val: {self.autobrightness_result}")

                self.next_state()

    @pyqtSlot(np.ndarray)
    def run_cellfinder(self, img):
        if self.cellfinder_result == None: 
            try:
                self.cellfinder_routine.send(img)
            except StopIteration as e:
                self.cellfinder_result = e.value

                if isinstance(self.cellfinder_result, bool):
                    print("Unable to find cells")
                elif isinstance(self.cellfinder_result, int):
                    print(f"Cells found @ motor pos: {self.cellfinder_result}")

                    self.next_state()

    @pyqtSlot(np.ndarray)
    def run_SSAF(self, img):
        if self.SSAF_result == None:
            try:
                self.SSAF_routine.send(img)
            except StopIteration as e:
                self.SSAF_result = e.value
                print(f"SSAF complete, motor moved by: {self.SSAF_result} steps")
                
                self.next_state()

    @pyqtSlot(np.ndarray)
    def run_fastflow(self, img):
        if self.fastflow_result == None:
            try:
                self.fastflow_routine.send(img)
            except StopIteration as e:
                self.fastflow_result = e.value

                if isinstance(self.fastflow_result, bool):
                    print("Unable to achieve flowrate - syringe at max position but flowrate is below target.")
                elif isinstance(self.fastflow_result, float):
                    print(f"Flowrate: {self.fastflow_result}")

                self.next_state()

    @pyqtSlot(np.ndarray)
    def run_experiment(self, img):
        # self.mscope.data_storage.writeData(img, fake_per_img_metadata)
        # TODO get metadata from hardware here

        # Periodically adjust focus using single shot autofocus
        self.PSSAF_routine.send(img)

        # Adjust the flow
        try:
            self.flowcontrol_routine.send(img)
        except CantReachTargetFlowrate:
            print("Can't reach target flowrate.")

        print("Running experiment")


class Acquisition(QObject):
    update_liveview = pyqtSignal(np.ndarray)
    update_scopeop = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        self.mscope = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.get_img)
        # self.timer.start(_UPDATE_PERIOD)

        self.running = True
        self.count = 0
        
        self.a = 0
        self.b = 0

    def get_mscope(self, mscope):
        self.mscope = mscope

    def get_img(self):

        try: 
            self.a = perf_counter()
            print("GET IMG {}".format(self.a-self.b))
            self.b = self.a    

            img = next(self.mscope.camera.yieldImages())
            self.update_liveview.emit(img)
            self.update_scopeop.emit(img)
            self.count += 1
        except Exception as e:
            # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
            # Once that happens, this can be swapped to catch the PyCameraException
            print(e)
            print(traceback.format_exc())
            

class Oracle(Machine):

    def __init__(self, *args, **kwargs):
        # Instantiate windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)
        # self.acquisition_thread.started.connect(self.acquisition.run)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp(self.acquisition.update_scopeop)
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Configure state machine
        states = [
            {'name' : 'standby'},
            {'name' : 'precheck', 
                'on_enter' : [self._start_precheck]},
            {'name' : 'form', 
                'on_enter' : [self._start_form], 
                'on_exit' : [self._close_form]},
            {'name' : 'liveview', 
                'on_enter' : [self._start_liveview], 
                'on_exit' : [self._close_liveview]},
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

        # Start scopeop thread
        self.scopeop_thread.start()

        # Trigger first transition
        self.to_precheck()

    def _freeze_liveview(self, freeze):
        if freeze:
            self.acquisition.update_liveview.disconnect(self.liveview_window.update_img)
        else:            
            self.acquisition.update_liveview.connect(self.liveview_window.update_img)

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
        self.timer.stop()
        self.acquisition.count = 0
        # delete current scope?

    def _start_precheck(self, *args):
        self.scopeop.precheck()
        self.acquisition.get_mscope(self.scopeop.mscope)

    def _start_form(self, *args):
        self.form_window.show()

    def _save_form(self, *args):
        try:
            # TBD implement actual save here
            # self.scopeop.mscope.data_storage.createNewExperiment(self.form_window.get_form_input())
            pass
        # TODO target correct exception here
        except Exception as e:
            print(e)
            _ = self._display_message(
                QMessageBox.Icon.Warning,
                "Invalid form input",
                "The following entries are invalid:",   # Add proper warnings here
                exit_after=True,
                )

        self.next_state()

    def _close_form(self, *args):
        self.form_window.close()

    def _start_liveview(self, *args):
        self.liveview_window.show()

        self.acquisition.update_liveview.connect(self.liveview_window.update_img)
        self.acquisition_thread.start()

        self.scopeop.start()
        
        self.acquisition.timer.start(_UPDATE_PERIOD)

    def _close_liveview(self, *args):
        self.scopeop.to_standby()
        self.acquisition.update_liveview.disconnect(self.liveview_window.update_img)

        self.liveview_window.close()

    def end(self, *args):
        # closing_file_future = self.scopeop.mscope.data_storage.close()
        self.scopeop.mscope.pneumatic_module.setDutyCycle(self.scopeop.mscope.pneumatic_module.getMaxDutyCycle())

        print("Waiting for the file to finish closing...")
        # while not closing_file_future.done():
        #     sleep(1)
        print("Successfully closed file.")

        # self.acquisition.running = False
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()
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