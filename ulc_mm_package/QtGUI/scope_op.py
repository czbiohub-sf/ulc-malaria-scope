import traceback
import numpy as np

from transitions import Machine, State
from time import perf_counter, sleep

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal, pyqtSlot

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE, PER_IMAGE_METADATA_KEYS
from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
)

class ScopeOpState(State):

    def __init__(self, name, on_enter=None, on_exit=None, ignore_invalid_triggers=None,
                signal=None, slot=None):

        self.signal = signal
        self.slot = slot

        if self.signal == None or self.slot == None:
            if (not self.signal == None) or (not self.slot == None):
                raise ValueError(f'Signal and/or slot specification is missing for state {name}.')

        # Connect signals/slots before "on_enter" events, and disconnect before "on_exit"
        else:
            if on_enter == None:
                on_enter = self._connect
            else:
                # on_enter.insert(0, self._connect)
                on_enter.append(self._connect)
        
            # if on_exit == None:
            #     on_exit = self._disconnect
            # else:
            #     on_exit.insert(0, self._disconnect)

        super().__init__(name, on_enter, on_exit, ignore_invalid_triggers)

    def _connect(self):
        print("CONNECTING " + self.name)
        self.signal.connect(self.slot)

    # def _disconnect(self):
    #     print("DISCONNECTING " + self.name)
    #     self.signal.disconnect(self.slot)

        
class ScopeOp(QObject, Machine):
    precheck_done = pyqtSignal()
    freeze_liveview = pyqtSignal(bool)
    error = pyqtSignal(str, str)
    set_fps = pyqtSignal(float)

    # state_cls = ScopeOpState

    def __init__(self, img_signal):
        super().__init__()

        self.mscope = MalariaScope()
        self.img_signal = img_signal

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None
        
        self.a = 0
        self.b = 0
        self.c = 0
        self.d = 0

        states = [
            {'name' : 'standby',
                'on_enter' : [self._reset]},
            {'name' : 'autobrightness', 
                'on_enter' : [self._start_autobrightness],
                # 'signal' : self.img_signal, 
                # 'slot' : self.run_autobrightness,
                },
            {'name' : 'cellfinder',
                'on_enter' : [self._start_cellfinder],
                # 'on_enter' : [self._start_cellfinder, self._freeze_liveview],
                #'on_exit' : [self._unfreeze_liveview],
                # 'signal' : self.img_signal, 
                # 'slot' : self.run_cellfinder,
                },
            {'name' : 'SSAF', 
                'on_enter' : [self._start_SSAF],
                # 'signal' : self.img_signal, 
                # 'slot' : self.run_SSAF,
                },
            # {'name' : 'fastflow', 
            #    'on_enter' : [self._start_fastflow],
            #    # 'signal' : self.img_signal, 
            #    # 'slot' : self.run_fastflow,
            #    },
            {'name' : 'experiment', 
                'on_enter' : [self._start_experiment],
                'on_exit' : [self._end_experiment],
                # 'signal' : self.img_signal, 
                # 'slot' : self.run_experiment,
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
        
        self.set_fps.emit(LIVEVIEW_PERIOD)
        
        self.img_signal.connect(self.run_experiment)
        
    def _end_experiment(self):
        self.img_signal.disconnect(self.run_experiment)
        self.set_fps.emit(ACQUISITION_PERIOD)

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
            #self.next_state()
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
            self.to_standby()
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
            # print("RECONNECTING")
            self.img_signal.connect(self.run_SSAF)

    @pyqtSlot(np.ndarray)
    def run_fastflow(self, img):
        self.img_signal.disconnect(self.run_fastflow)

        try:
            self.fastflow_routine.send(img)
        except CantReachTargetFlowrate:
            self.fastflow_result = -1
            print("Unable to achieve flowrate - syringe at max position but flowrate is below target.")
            self.error.emit("Calibration failed", "Unable to achieve desired flowrate.")
            self.to_standby()
        except StopIteration as e:
            self.fastflow_result = e.value
            print(f"Flowrate: {self.fastflow_result}")
            self.next_state()
        else:
            self.img_signal.connect(self.run_fastflow)

    @pyqtSlot(np.ndarray)
    def run_experiment(self, img):

        self.c = perf_counter()
            
        # self.mscope.data_storage.writeData(img, fake_per_img_metadata)
        # TODO get metadata from hardware here

        # Periodically adjust focus using single shot autofocus
        self.PSSAF_routine.send(img)

        # Adjust the flow
        try:
            self.flowcontrol_routine.send(img)
        except CantReachTargetFlowrate:
            print("Can't reach target flowrate.")
        
        self.d = perf_counter()
            
        # print("RUN: {}".format(self.c-self.d))
