""" Low-level/hardware state machine manager

Controls hardware (ie. the Scope) operations.
Manages hardware routines and interactions with Oracle and Acquisition.

"""

import numpy as np

from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *
from ulc_mm_package.hardware.hardware_constants import SIMULATION
from ulc_mm_package.image_processing.processing_constants import (
    TARGET_FLOWRATE,
    PER_IMAGE_METADATA_KEYS,
)
from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
    MAX_FRAMES,
)


class ScopeOp(QObject, Machine):
    setup_done = pyqtSignal()
    experiment_done = pyqtSignal()
    reset_done = pyqtSignal()

    error = pyqtSignal(str, str)

    create_timers = pyqtSignal()
    start_timers = pyqtSignal()
    stop_timers = pyqtSignal()

    set_period = pyqtSignal(float)
    freeze_liveview = pyqtSignal(bool)

    def __init__(self, img_signal):
        super().__init__()

        self.mscope = None
        self.img_signal = img_signal

        # TODO make sure all of these get reset

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None
        self.count = 0

        states = [
            {
                "name": "standby",
            },
            {
                "name": "autobrightness",
                "on_enter": [self._start_autobrightness],
            },
            {
                "name": "cellfinder",
                "on_enter": [self._start_cellfinder],
            },
            {
                "name": "SSAF",
                "on_enter": [self._start_SSAF],
            },
            {
                "name": "fastflow",
                "on_enter": [self._start_fastflow],
            },
            {
                "name": "experiment",
                "on_enter": [self._start_experiment],
            },
            {
                "name": "intermission",
                "on_enter": [self._end_experiment, self._start_intermission],
            },
        ]

        Machine.__init__(self, states=states, queued=True, initial="standby")
        self.add_ordered_transitions()
        self.add_transition(
            trigger="rerun", source="intermission", dest="standby", before="reset"
        )
        self.add_transition(
            trigger="stop", source="*", dest="standby", before="_end_experiment"
        )

    def setup(self):
        print("SCOPEOP: Creating timers...")
        self.create_timers.emit()

        print("SCOPEOP: Initializing scope...")
        self.mscope = MalariaScope()
        component_status = self.mscope.getComponentStatus()

        if all([status == True for status in component_status.values()]):
            self.setup_done.emit()
        else:
            failed_components = [
                comp.name
                for comp in component_status
                if component_status.get(comp) == False
            ]
            self.error.emit(
                "Hardware pre-check failed",
                "The following component(s) could not be instantiated: {}.".format(
                    (",".join(failed_components)).capitalize()
                ),
            )

    def start(self):
        self.start_timers.emit()

        self.next_state()

    def reset(self):
        print("SCOPEOP: Resetting pneumatic module")
        self.mscope.pneumatic_module.setDutyCycle(
            self.mscope.pneumatic_module.getMaxDutyCycle()
        )

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.SSAF_result = None
        self.fastflow_result = None

        self.count = 0

        self.set_period.emit(ACQUISITION_PERIOD)
        self.reset_done.emit()

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def _start_autobrightness(self):
        print("SCOPEOP: Starting autobrightness")

        self.autobrightness_routine = autobrightnessRoutine(self.mscope)
        self.autobrightness_routine.send(None)

        self.img_signal.connect(self.run_autobrightness)

    def _start_cellfinder(self):
        print("SCOPEOP: Starting cellfinder")

        self.cellfinder_routine = find_cells_routine(self.mscope)
        self.cellfinder_routine.send(None)

        self.img_signal.connect(self.run_cellfinder)

    def _start_SSAF(self):
        print("SCOPEOP: Starting SSAF")

        print(f"Moving motor to {self.cellfinder_result}")
        self.mscope.motor.move_abs(self.cellfinder_result)

        self.SSAF_routine = singleShotAutofocusRoutine(self.mscope, None)
        self.SSAF_routine.send(None)

        self.img_signal.connect(self.run_SSAF)

    def _start_fastflow(self):
        print("SCOPEOP: Starting fastflow")

        self.fastflow_routine = fastFlowRoutine(self.mscope, None)
        self.fastflow_routine.send(None)

        self.img_signal.connect(self.run_fastflow)

    def _start_experiment(self):
        print("SCOPEOP: Starting experiment")

        self.PSSAF_routine = periodicAutofocusWrapper(self.mscope, None)
        self.PSSAF_routine.send(None)

        self.flowcontrol_routine = flowControlRoutine(
            self.mscope, TARGET_FLOWRATE, None
        )
        self.flowcontrol_routine.send(None)

        self.set_period.emit(LIVEVIEW_PERIOD)

        self.img_signal.connect(self.run_experiment)

    def _end_experiment(self):
        print("SCOPEOP: Ending experiment")
        self.stop_timers.emit()

        print("SCOPEOP: Turning off LED")
        self.mscope.led.turnOff()

        # TODO close data_storage

    def _start_intermission(self):
        self.experiment_done.emit()

    @pyqtSlot(np.ndarray)
    def run_autobrightness(self, img):
        self.img_signal.disconnect(self.run_autobrightness)

        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.autobrightness_result = e.value
            print(f"Mean pixel val: {self.autobrightness_result}")
            self.next_state()
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
        except InvalidMove:
            self.error.emit(
                "Calibration failed",
                "Unable to achieve desired focus within condenser's depth of field.",
            )
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
            if SIMULATION:
                self.fastflow_result = 8  # rough estimate of slow flowrate
                print(f"Flowrate: {self.fastflow_result}")
                self.next_state()
            else:
                self.fastflow_result = -1
                self.error.emit(
                    "Calibration failed",
                    "Unable to achieve desired flowrate with syringe at max position.",
                )
        except StopIteration as e:
            self.fastflow_result = e.value
            print(f"Flowrate: {self.fastflow_result}")
            self.next_state()
        else:
            self.img_signal.connect(self.run_fastflow)

    @pyqtSlot(np.ndarray)
    def run_experiment(self, img):
        self.img_signal.disconnect(self.run_experiment)

        if self.count >= MAX_FRAMES:
            print("Reached frame timeout for experiment")
            self.to_intermission()
        else:
            prev_res = count_parasitemia(self.mscope, img)

            # Adjust the flow
            try:
                # Periodically adjust focus using single shot autofocus
                self.PSSAF_routine.send(img)
                # TODO add density check here
                self.flowcontrol_routine.send(img)
            except CantReachTargetFlowrate:
                if not SIMULATION:
                    self.error.emit(
                        "Flow control failed",
                        "Unable to achieve desired flowrate with syringe at max position.",
                    )
            # TODO add recovery operation for low cell density
            except:
                self.error.emit(
                    "Autofocus failed",
                    "Unable to achieve desired focus within condenser's depth of field.",
                )
            else:
                self.count += 1
                self.img_signal.connect(self.run_experiment)
