import traceback
import numpy as np

from transitions import Machine, State
from time import perf_counter, sleep

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal, pyqtSlot, QThread

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE, PER_IMAGE_METADATA_KEYS
from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
)

class ScopeOp(QObject, Machine):
    setup_done = pyqtSignal()
    reset_done = pyqtSignal()
    freeze_liveview = pyqtSignal(bool)
    error = pyqtSignal(str, str)
    set_period = pyqtSignal(float)
    create_timers = pyqtSignal()
    start_timers = pyqtSignal()
    stop_timers = pyqtSignal()

    def __init__(self, img_signal):
        super().__init__()

        self.mscope = MalariaScope()
        self.img_signal = img_signal

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None

        self.count = 0
        
        # self.a = 0
        # self.b = 0
        # self.c = 0
        # self.d = 0

        states = [
            {'name' : 'standby'},
            {'name' : 'autobrightness', 
                'on_enter' : [self._start_autobrightness],
                },
            {'name' : 'cellfinder',
                'on_enter' : [self._start_cellfinder, self._freeze_liveview],
                'on_exit' : [self._unfreeze_liveview],
                },
            {'name' : 'SSAF', 
                'on_enter' : [self._start_SSAF],
                },
            # {'name' : 'fastflow', 
            #    'on_enter' : [self._start_fastflow],
            #    },
            {'name' : 'experiment', 
                'on_enter' : [self._start_experiment],
                'on_exit' : [self._end_experiment],
                },
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='reset', source='*', dest='standby', before='_reset')

    def setup(self):
        print("Creating timers")
        self.create_timers.emit()  

        component_status = self.mscope.getComponentStatus()
        print(component_status)

        # TEMP for testing
        if True:
        # if all([status==True for status in component_status.values()]):
            self.setup_done.emit()
            print("Successful setup")
        else: 
            failed_components = [comp.name for comp in component_status if component_status.get(comp)==False]
            self.error.emit(
                "Hardware pre-check failed",
                "The following component(s) could not be instantiated: {}."
                    .format((",".join(failed_components)).capitalize()),
                )
            print("Failed setup")

    def start(self):
        print(self.state)
        self.start_timers.emit()

        if not self.state == 'standby':
            self.error.emit(
                "Invalid startup state", 
                "Scopeop can only be started from state 'standby', but is currently in state '{}'.".format(self.state)
                )

        self.next_state()
        
    def shutoff(self):
        self.mscope.shutoff()
        self.stop_timers.emit()

    def _reset(self):
        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None

        self.count = 0

        self.set_period.emit(ACQUISITION_PERIOD)

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def _start_autobrightness(self):
        self.autobrightness_routine = autobrightnessRoutine(self.mscope)
        self.autobrightness_routine.send(None)
        
        self.img_signal.connect(self.run_autobrightness)

    def _start_cellfinder(self):       
        self.cellfinder_routine = find_cells_routine(self.mscope)
        self.cellfinder_routine.send(None)
        
        self.img_signal.connect(self.run_cellfinder)

    def _start_SSAF(self):
        print(f"Moving motor to {self.cellfinder_result}")
        self.mscope.motor.move_abs(self.cellfinder_result)

        self.SSAF_routine = singleShotAutofocusRoutine(self.mscope, None)
        self.SSAF_routine.send(None)
        
        self.img_signal.connect(self.run_SSAF)

    def _start_fastflow(self):
        self.fastflow_routine = fastFlowRoutine(self.mscope, None)
        self.fastflow_routine.send(None)
        
        self.img_signal.connect(self.run_fastflow)

    def _start_experiment(self):
        self.PSSAF_routine = periodicAutofocusWrapper(self.mscope, None)
        self.PSSAF_routine.send(None)
        
        self.flowcontrol_routine = flowControlRoutine(self.mscope, TARGET_FLOWRATE, None)
        self.flowcontrol_routine.send(None)
        
        self.set_period.emit(LIVEVIEW_PERIOD)
        
        self.img_signal.connect(self.run_experiment)
        
    def _end_experiment(self):
        print("DONE")
        self.stop_timers.emit()

        self.reset()
        self.reset_done.emit()

    @pyqtSlot(np.ndarray)
    def run_autobrightness(self, img):
        self.img_signal.disconnect(self.run_autobrightness)
        
        # self.a = perf_counter()
        # print("AB: {}".format(self.a-self.b))
        # self.b = self.a   

        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.autobrightness_result = e.value
            print(f"Mean pixel val: {self.autobrightness_result}")
            self.to_experiment()
        else:
            self.img_signal.connect(self.run_autobrightness)

    @pyqtSlot(np.ndarray)
    def run_cellfinder(self, img):
        self.img_signal.disconnect(self.run_cellfinder)

        try:
            self.cellfinder_routine.send(img)
        except StopIteration as e:
            self.cellfinder_result = e.value
            print(f"Cells found @ motor pos: {self.cellfinder_result}")
            self.next_state()
        except NoCellsFound:
            self.cellfinder_result = -1
            self.error.emit("Calibration failed", "No cells found.")
        else:
            self.img_signal.connect(self.run_cellfinder)

    @pyqtSlot(np.ndarray)
    def run_SSAF(self, img):
        self.img_signal.disconnect(self.run_SSAF)

        try:
            self.SSAF_routine.send(img)
        except StopIteration as e:
            self.SSAF_result = e.value
            print(f"SSAF complete, motor moved by: {self.SSAF_result} steps")
            self.next_state()
        else:
            self.img_signal.connect(self.run_SSAF)

    @pyqtSlot(np.ndarray)
    def run_fastflow(self, img):
        self.img_signal.disconnect(self.run_fastflow)

        try:
            self.fastflow_routine.send(img)
        except CantReachTargetFlowrate:
            self.fastflow_result = -1
            self.error.emit("Calibration failed", "Unable to achieve desired flowrate with syringe at max position.")
        except StopIteration as e:
            self.fastflow_result = e.value
            print(f"Flowrate: {self.fastflow_result}")
            self.next_state()
        else:
            self.img_signal.connect(self.run_fastflow)

    @pyqtSlot(np.ndarray)
    def run_experiment(self, img):
        self.img_signal.disconnect(self.run_experiment)

        # self.c = perf_counter()
            
        # self.mscope.data_storage.writeData(img, fake_per_img_metadata)
        # TODO get metadata from hardware here

        # Periodically adjust focus using single shot autofocus
        self.PSSAF_routine.send(img)

        # Adjust the flow
        try:
            self.flowcontrol_routine.send(img)
        except CantReachTargetFlowrate:
            print("Can't reach target flowrate.")
            # self.error.emit("Calibration failed", "Unable to achieve desired flowrate with syringe at max position.")
        
        # self.d = perf_counter()
            
        # print("RUN: {}".format(self.c-self.d))

        print(self.count)
        self.count += 1

        if self.count >= 10:
            print("DONE DONE DONE")
            self.to_standby()
        else:
            self.img_signal.connect(self.run_experiment)


