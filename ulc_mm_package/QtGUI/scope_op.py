""" Mid-level/hardware state machine manager

Controls hardware (ie. the Scope) operations.
Manages hardware routines and interactions with Oracle and Acquisition.

"""

import numpy as np

from datetime import datetime
from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *

from ulc_mm_package.scope_constants import PER_IMAGE_METADATA_KEYS
from ulc_mm_package.hardware.hardware_constants import SIMULATION, DATETIME_FORMAT
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE
from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
    MAX_FRAMES,
    STATUS,
)

# TODO populate info?
# TODO remove -1 flag from TH sensor?


class ScopeOp(QObject, Machine):
    setup_done = pyqtSignal()
    experiment_done = pyqtSignal()
    reset_done = pyqtSignal()

    yield_mscope = pyqtSignal(MalariaScope)

    error = pyqtSignal(str, str)

    create_timers = pyqtSignal()
    start_timers = pyqtSignal()
    stop_timers = pyqtSignal()

    set_period = pyqtSignal(float)
    freeze_liveview = pyqtSignal(bool)

    update_state = pyqtSignal(str)
    update_img_count = pyqtSignal(int)
    update_cell_count = pyqtSignal(list)
    update_msg = pyqtSignal(str)

    update_flowrate = pyqtSignal(int)
    update_focus = pyqtSignal(int)

    def __init__(self, img_signal):
        super().__init__()

        self._init_variables()
        self.mscope = None
        self.img_signal = img_signal

        self.digits = int(np.log10(MAX_FRAMES - 1)) + 1

        states = [
            {
                "name": "standby",
            },
            {
                "name": "autobrightness",
                "on_enter": [self.send_state, self._start_autobrightness],
            },
            {
                "name": "cellfinder",
                "on_enter": [self.send_state, self._start_cellfinder],
            },
            {
                "name": "autofocus",
                "on_enter": [self.send_state, self._start_autofocus],
            },
            {
                "name": "fastflow",
                "on_enter": [self.send_state, self._start_fastflow],
            },
            {
                "name": "experiment",
                "on_enter": [self.send_state, self._start_experiment],
            },
            {
                "name": "intermission",
                "on_enter": [self._end_experiment, self._start_intermission],
            },
        ]

        if SIMULATION:
            skipped_states = ["autofocus", "fastflow"]
            states = [entry for entry in states if entry["name"] not in skipped_states]

        Machine.__init__(self, states=states, queued=True, initial="standby")
        self.add_ordered_transitions()
        self.add_transition(
            trigger="rerun", source="intermission", dest="standby", before="reset"
        )

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def send_state(self):
        # TODO perhaps delete this to print more useful statements. See future "logging" branch
        self.update_msg.emit(f"Changing state to {self.state}")

        self.update_state.emit(self.state)

    def _init_variables(self):

        self.img_metadata = {key: None for key in PER_IMAGE_METADATA_KEYS}

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.autofocus_result = None
        self.fastflow_result = None
        self.count = 0

        self.update_img_count.emit(0)
        self.update_msg.emit("Starting new experiment")

    def setup(self):
        print("SCOPEOP: Creating timers...")
        self.create_timers.emit()

        print("SCOPEOP: Initializing scope...")
        self.mscope = MalariaScope()
        self.yield_mscope.emit(self.mscope)
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
                    (", ".join(failed_components)).capitalize()
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

        # Reset variables
        self._init_variables()

        self.set_period.emit(ACQUISITION_PERIOD)
        self.reset_done.emit()

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

    def _start_autofocus(self):
        print("SCOPEOP: Starting autofocus")

        print(f"Moving motor to {self.cellfinder_result}")
        self.mscope.motor.move_abs(self.cellfinder_result)

        self.autofocus_routine = singleShotAutofocusRoutine(self.mscope, None)
        self.autofocus_routine.send(None)

        self.img_signal.connect(self.run_autofocus)

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

        self.density_routine = cell_density_routine(None)
        self.density_routine.send(None)

        self.set_period.emit(LIVEVIEW_PERIOD)

        self.img_signal.connect(self.run_experiment)

    def _end_experiment(self):

        # TODO is there a better way to check for pyqtSignal connections?
        try:
            self.img_signal.disconnect()
            print("SCOPEOP: Disconnected img_signal")
        except TypeError:
            print("SCOPEOP: Since img_signal is already disconnected, no changes made")

        print("SCOPEOP: Ending experiment")
        self.stop_timers.emit()

        print("SCOPEOP: Turning off LED")
        self.mscope.led.turnOff()

        print("SCOPEOP: Closing data storage")
        self.mscope.data_storage.close()

    def _start_intermission(self):
        self.experiment_done.emit()

    @pyqtSlot(np.ndarray, float)
    def run_autobrightness(self, img, _timestamp):
        self.img_signal.disconnect(self.run_autobrightness)

        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.autobrightness_result = e.value
            print(f"SCOPEOP: Mean pixel val = {self.autobrightness_result}")
            # TODO save autobrightness value to metadata instead
            self.next_state()
        except BrightnessTargetNotAchieved as e:
            self.autobrightness_result = e.value
            print(
                f"SCOPEOP: Brightness not quite high enough but still ok - mean pixel val = {self.autobrightness_result}"
            )
            self.next_state()
        except BrightnessCriticallyLow as e:
            self.error.emit(
                "Autobrightness failed",
                f"Too dim to run an experiment - aborting. Mean pixel value: {e.value}",
            )
        else:
            self.img_signal.connect(self.run_autobrightness)

    @pyqtSlot(np.ndarray, float)
    def run_cellfinder(self, img, _timestamp):
        self.img_signal.disconnect(self.run_cellfinder)

        try:
            self.cellfinder_routine.send(img)
        except StopIteration as e:
            self.cellfinder_result = e.value
            print(f"SCOPEOP: Cells found @ motor pos = {self.cellfinder_result}")
            self.next_state()
        except NoCellsFound:
            self.cellfinder_result = -1
            self.error.emit("Calibration failed", "No cells found.")
        else:
            self.img_signal.connect(self.run_cellfinder)

    @pyqtSlot(np.ndarray, float)
    def run_autofocus(self, img, _timestamp):
        self.img_signal.disconnect(self.run_autofocus)

        try:
            self.autofocus_routine.send(img)
        except InvalidMove:
            self.error.emit(
                "Calibration failed",
                "Unable to achieve desired focus within condenser's depth of field.",
            )
        except StopIteration as e:
            self.autofocus_result = e.value
            print(
                f"SCOPEOP: Autofocus complete, motor moved by {self.autofocus_result} steps"
            )
            self.next_state()
        else:
            self.img_signal.connect(self.run_autofocus)

    @pyqtSlot(np.ndarray, float)
    def run_fastflow(self, img, timestamp):
        self.img_signal.disconnect(self.run_fastflow)

        try:
            self.fastflow_routine.send((img, timestamp))
        except CantReachTargetFlowrate:
            if SIMULATION:
                self.fastflow_result = TARGET_FLOWRATE
                print(f"SCOPEOP: Flowrate (simulated) = {int(self.fastflow_result)}")
                self.update_flowrate.emit(int(self.fastflow_result))
                # TODO save flowrate result to metadata instead
                self.next_state()
            else:
                self.fastflow_result = -1
                self.error.emit(
                    "Calibration failed",
                    "Unable to achieve desired flowrate with syringe at max position.",
                )
        except StopIteration as e:
            self.fastflow_result = e.value
            print(f"SCOPEOP: Flowrate = {self.fastflow_result}")
            self.update_flowrate.emit(self.fastflow_result)
            self.next_state()
        else:
            self.img_signal.connect(self.run_fastflow)

    @pyqtSlot(np.ndarray, float)
    def run_experiment(self, img, timestamp):
        self.img_signal.disconnect(self.run_experiment)

        if self.count >= MAX_FRAMES:
            self.to_intermission()
        else:
            # Record timestamp before running routines
            self.img_metadata["timestamp"] = datetime.now().strftime(DATETIME_FORMAT)
            self.img_metadata["im_counter"] = f"{self.count:0{self.digits}d}"

            self.update_img_count.emit(self.count)

            prev_res = count_parasitemia(self.mscope, img, [self.count])
            # TODO update cell counts here, where cell_counts=[healthy #, ring #, schizont #, troph #]
            # self.update_cell_count.emit(cell_counts)

            # Adjust the flow
            try:
                # Periodic routines
                focus_err = self.PSSAF_routine.send(img)
                # TEMP comment out density because it runs slow
                # density = self.density_routine.send(img)
                flowrate = self.flowcontrol_routine.send((img, timestamp))
            except LowDensity:
                # TODO add recovery operation for low cell density
                print("LOW CELL DENSITY")
                pass
            except CantReachTargetFlowrate:
                if not SIMULATION:
                    self.error.emit(
                        "Flow control failed",
                        "Unable to achieve desired flowrate with syringe at max position.",
                    )
                    return
            except MotorControllerError as e:
                if not SIMULATION:
                    self.error.emit(
                        "Autofocus failed",
                        "Unable to achieve desired focus within condenser's depth of field.",
                    )
                    return

            # Update infopanel
            if focus_err != None:
                # TODO change this to non int?
                self.update_focus.emit(int(focus_err))
            if flowrate != None:
                self.update_flowrate.emit(int(flowrate))

            # Update remaining metadata
            self.img_metadata["motor_pos"] = self.mscope.motor.getCurrentPosition()
            self.img_metadata[
                "pressure_hpa"
            ] = self.mscope.pneumatic_module.getPressure()
            self.img_metadata[
                "syringe_pos"
            ] = self.mscope.pneumatic_module.getCurrentDutyCycle()
            self.img_metadata["flowrate"] = flowrate
            self.img_metadata["focus_error"] = focus_err
            # TEMP comment out density because it runs slow
            # self.img_metadata["cell_density"] = density
            self.img_metadata[
                "temperature"
            ] = self.mscope.ht_sensor.getRelativeHumidity()
            self.img_metadata["humidity"] = self.mscope.ht_sensor.getTemperature()

            self.mscope.data_storage.writeData(img, self.img_metadata)

            self.count += 1
            self.img_signal.connect(self.run_experiment)
