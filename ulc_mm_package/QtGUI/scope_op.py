""" Mid-level/hardware state machine manager

Controls hardware (ie. the Scope) operations.
Manages hardware routines and interactions with Oracle and Acquisition.

"""

import numpy as np
import logging

from transitions import Machine
from time import sleep
from typing import Any

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.hardware.scope_routines import *

from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.scope_constants import (
    PER_IMAGE_METADATA_KEYS,
    SIMULATION,
    MAX_FRAMES,
    VERBOSE,
)
from ulc_mm_package.hardware.hardware_modules import PressureSensorStaleValue
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.neural_nets.NCSModel import AsyncInferenceResult
from ulc_mm_package.neural_nets.YOGOInference import YOGO, ClassCountResult
from ulc_mm_package.neural_nets.neural_network_constants import (
    AF_BATCH_SIZE,
    YOGO_CLASS_LIST,
    YOGO_PERIOD_S
)
from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
    STATUS,
    TH_PERIOD,
)

# TODO populate info?
# TODO remove -1 flag from TH sensor?


class ScopeOp(QObject, Machine):
    setup_done = pyqtSignal()
    experiment_done = pyqtSignal()
    reset_done = pyqtSignal()

    yield_mscope = pyqtSignal(MalariaScope)

    error = pyqtSignal(str, str, bool)

    send_pause = pyqtSignal(str, str)

    create_timers = pyqtSignal()
    start_timers = pyqtSignal()
    stop_timers = pyqtSignal()

    set_period = pyqtSignal(float)
    freeze_liveview = pyqtSignal(bool)

    update_state = pyqtSignal(str)
    update_img_count = pyqtSignal(int)
    update_cell_count = pyqtSignal(ClassCountResult)
    update_msg = pyqtSignal(str)

    update_flowrate = pyqtSignal(float)
    update_focus = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        self.acquisition = Acquisition()
        self.img_signal = self.acquisition.update_scopeop

        self.mscope = None
        self.digits = int(np.log10(MAX_FRAMES - 1)) + 1
        self._set_variables()

        states = [
            {
                "name": "pause",
                "on_enter": [self._send_state, self._start_pause],
                "on_exit": [self._end_pause],
            },
            {
                "name": "standby",
                "on_enter": [self._send_state],
            },
            {
                "name": "autobrightness_precells",
                "on_enter": [self._send_state, self._start_autobrightness_precell],
            },
            {
                "name": "pressure_check",
                "on_enter": [self._send_state, self._check_pressure_seal],
            },
            {
                "name": "cellfinder",
                "on_enter": [self._send_state, self._start_cellfinder],
            },
            {
                "name": "autobrightness_postcells",
                "on_enter": [self._send_state, self._start_autobrightness_postcell],
            },
            {
                "name": "autofocus",
                "on_enter": [self._send_state, self._start_autofocus],
            },
            {
                "name": "fastflow",
                "on_enter": [self._send_state, self._start_fastflow],
            },
            {
                "name": "experiment",
                "on_enter": [self._send_state, self._start_experiment],
            },
            {
                "name": "intermission",
                "on_enter": [
                    self._end_experiment,
                    self._send_state,
                    self._start_intermission,
                ],
            },
        ]

        if SIMULATION:
            # Fastflow state is defined but skipped in simulation mode, see _start_fastflow
            skipped_states = [
                "autofocus",
                "autobrightness_precells",
                "autobrightness_postcells",
                "pressure_check",
            ]
            states = [entry for entry in states if entry["name"] not in skipped_states]

        Machine.__init__(self, states=states, queued=True, initial="standby")
        self.add_ordered_transitions()
        self.add_transition(
            trigger="rerun", source="intermission", dest="standby", before="reset"
        )
        self.add_transition(
            trigger="unpause", source="pause", dest="autobrightness_precells"
        )

    def _set_variables(self):
        self.running = None

        self.autofocus_batch = []
        self.img_metadata = {key: None for key in PER_IMAGE_METADATA_KEYS}

        self.target_flowrate = None

        self.autobrightness_result = None
        self.cellfinder_result = None
        self.autofocus_result = None
        self.fastflow_result = None

        self.count = 0
        self.cell_counts = np.zeros(len(YOGO_CLASS_LIST), dtype=int)

        self.TH_time = None
        self.start_time = None

        self.update_img_count.emit(0)
        self.update_msg.emit("Starting new experiment")

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def _send_state(self):
        # TODO perhaps delete this to print more useful statements. See future "logging" branch
        state_name = self.state.split("_")[0]

        if self.state != "standby":
            self.update_msg.emit(f"{state_name.capitalize()} in progress...")

        self.logger.info(f"Changing state to {self.state}.")
        self.update_state.emit(state_name)

    def setup(self):
        self.create_timers.emit()

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
                True,
            )

    def start(self):
        self.running = True
        self.start_timers.emit()
        self.next_state()

    def reset(self):
        # Reset variables
        self._set_variables()

        self.set_period.emit(ACQUISITION_PERIOD)
        self.reset_done.emit()

    def shutoff(self):
        self.running = False

        try:
            self.img_signal.disconnect()
            self.logger.info("Disconnected img_signal.")
        except TypeError:
            self.logger.info(
                "Since img_signal is already disconnected, no signal/slot changes were made."
            )

        self.stop_timers.emit()

    def _start_pause(self):
        self.running = False

        try:
            self.img_signal.disconnect()
        except TypeError:
            self.logger.info(
                "Since img_signal is already disconnected, no signal/slot changes were made."
            )

        self.logger.info("Resetting pneumatic module for pause.")
        self.mscope.pneumatic_module.setDutyCycle(
            self.mscope.pneumatic_module.getMaxDutyCycle()
        )
        self.mscope.led.turnOff()

    def _end_pause(self):
        self.mscope.led.turnOn()
        self.running = True

    def _start_autobrightness_precell(self):

        self.autobrightness_routine = autobrightnessRoutine(self.mscope)
        self.autobrightness_routine.send(None)

        self.img_signal.connect(self.run_autobrightness)

    def _check_pressure_seal(self):
        # Check that the pressure seal is good (i.e there is a sufficient pressure delta)
        try:
            pdiff = checkPressureDifference(self.mscope)
            self.logger.info(f"Pressure difference ok: {pdiff} hPa.")
            self.next_state()
        except PressureSensorBusy:
            self.logger.error(f"Unable to read value from the pressure sensor - {e}")
            # TODO What to do in a case where the sensor is acting funky?
            self.error.emit(
                "Calibration failed",
                "Failed to read pressure sensor to perform pressure seal check.",
                False,
            )
        except PressureLeak as e:
            self.logger.error(f"Improper seal / pressure leak detected - {e}")
            # TODO provide instructions for dealing with pressure leak?
            self.error.emit(
                "Calibration failed", "Improper seal / pressure leak detected.", False
            )

    def _start_cellfinder(self):
        self.cellfinder_routine = find_cells_routine(self.mscope)
        self.cellfinder_routine.send(None)

        self.img_signal.connect(self.run_cellfinder)

    def _start_autobrightness_postcell(self):
        self.logger.info(f"Moving motor to {self.cellfinder_result}.")
        self.mscope.motor.move_abs(self.cellfinder_result)

        self.autobrightness_routine = autobrightnessRoutine(self.mscope)
        self.autobrightness_routine.send(None)

        self.img_signal.connect(self.run_autobrightness)

    def _start_autofocus(self):
        self.img_signal.connect(self.run_autofocus)

    def _start_fastflow(self):
        if SIMULATION:
            self.logger.info(f"Skipping {self.state} state in simulation mode.")
            sleep(1)
            self.next_state()
            return

        self.fastflow_routine = fastFlowRoutine(
            self.mscope, None, target_flowrate=self.target_flowrate
        )
        self.fastflow_routine.send(None)

        self.img_signal.connect(self.run_fastflow)

    def _start_experiment(self):
        self.PSSAF_routine = periodicAutofocusWrapper(self.mscope, None)
        self.PSSAF_routine.send(None)

        self.flowcontrol_routine = flowControlRoutine(
            self.mscope, self.target_flowrate, None
        )
        self.flowcontrol_routine.send(None)

        self.density_routine = cell_density_routine()
        self.density_routine.send(None)

        self.count_parasitemia_routine = count_parasitemia_periodic_wrapper(self.mscope)
        self.count_parasitemia_routine.send(None)

        self.set_period.emit(LIVEVIEW_PERIOD)

        self.TH_time = perf_counter()
        self.start_time = perf_counter()
        self.last_time = perf_counter()

        self.img_signal.connect(self.run_experiment)

    def _end_experiment(self):
        self.shutoff()

        if self.start_time != None:
            self.logger.info(
                f"Net FPS is {self.count/(perf_counter()-self.start_time)}"
            )

        self.logger.info("Resetting pneumatic module for rerun.")
        self.mscope.pneumatic_module.setDutyCycle(
            self.mscope.pneumatic_module.getMaxDutyCycle()
        )
        self.mscope.led.turnOff()

        closing_file_future = self.mscope.data_storage.close()
        while not closing_file_future.done():
            sleep(1)

    def _start_intermission(self):
        self.experiment_done.emit()

    @pyqtSlot(np.ndarray, float)
    def run_autobrightness(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_autobrightness)

        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.autobrightness_result = e.value
            self.logger.info(
                f"Autobrightness successful. Mean pixel val = {self.autobrightness_result}."
            )
            self.next_state()
        except BrightnessTargetNotAchieved as e:
            self.autobrightness_result = e.value
            self.logger.warning(
                f"Autobrightness target not achieved, but still ok. Mean pixel val = {self.autobrightness_result}."
            )
            self.next_state()
        except BrightnessCriticallyLow as e:
            self.logger.error(
                f"Autobrightness failed. Mean pixel value = {e.value}.",
            )
            self.error.emit(
                "Autobrightness failed",
                "LED is too dim to run experiment.",
                False,
            )
        except LEDNoPower as e:
            self.logger.error(f"LED initial functionality test did not pass - {e}")
            self.error.emit("LED failure", "The off/on LED test failed.", False)
        else:
            if self.running:
                self.img_signal.connect(self.run_autobrightness)

    @pyqtSlot(np.ndarray, float)
    def run_cellfinder(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended")
            return

        self.img_signal.disconnect(self.run_cellfinder)

        try:
            self.cellfinder_routine.send(img)
        except StopIteration as e:
            self.cellfinder_result = e.value
            self.logger.info(
                f"Cellfinder successful. Cells found at motor pos = {self.cellfinder_result}."
            )
            self.next_state()
        except NoCellsFound:
            self.logger.error("Cellfinder failed. No cells found.")
            self.error.emit("Calibration failed", "No cells found.", False)
        else:
            if self.running:
                self.img_signal.connect(self.run_cellfinder)

    @pyqtSlot(np.ndarray, float)
    def run_autofocus(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_autofocus)

        if len(self.autofocus_batch) < AF_BATCH_SIZE:
            self.autofocus_batch.append(img)

            if self.running:
                self.img_signal.connect(self.run_autofocus)
        else:
            try:
                self.autofocus_result = singleShotAutofocusRoutine(
                    self.mscope, self.autofocus_batch
                )
                self.autofocus_batch = []
                self.logger.info(
                    f"Autofocus complete. Calculated focus error = {self.autofocus_result} steps."
                )
                self.next_state()
            except InvalidMove:
                self.logger.error(
                    "Autofocus failed. Can't achieve focus because the stage has reached its range of motion limit."
                )
                self.error.emit(
                    "Calibration failed",
                    "Unable to achieve focus because the stage has reached its range of motion limit..",
                    False,
                )

    @pyqtSlot(np.ndarray, float)
    def run_fastflow(self, img, timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_fastflow)

        try:
            flowrate = self.fastflow_routine.send((img, timestamp))

            if flowrate != None:
                self.update_flowrate.emit(flowrate)
        except CantReachTargetFlowrate:
            if SIMULATION:
                self.fastflow_result = self.target_flowrate
                self.logger.info(
                    f"Fastflow successful. Flowrate (simulated) = {self.fastflow_result}."
                )
                self.update_flowrate.emit(self.fastflow_result)
                self.next_state()
            else:
                self.fastflow_result = -1
                self.logger.error("Fastflow failed. Syringe already at max position.")
                self.error.emit(
                    "Calibration failed",
                    "Unable to achieve desired flowrate with syringe at max position.",
                    False,
                )
        except LowConfidenceCorrelations:
            if SIMULATION:
                self.fastflow_result = self.target_flowrate
                self.logger.info(
                    f"Fastflow successful. Flowrate (simulated) = {self.fastflow_result}."
                )
                self.update_flowrate.emit(self.fastflow_result)
                self.next_state()
            else:
                self.fastflow_result = -1
                self.logger.error(
                    "Fastflow failed. Too many recent low confidence xcorr calculations."
                )
                self.error.emit(
                    "Calibration failed",
                    "Too many recent low confidence xcorr calculations",
                    False,
                )
        except StopIteration as e:
            self.fastflow_result = e.value
            self.logger.info(f"Fastflow successful. Flowrate = {self.fastflow_result}.")
            self.update_flowrate.emit(self.fastflow_result)
            self.next_state()
        else:
            if self.running:
                self.img_signal.connect(self.run_fastflow)

    def _update_metadata_if_verbose(self, key: str, val: Any):
        if VERBOSE:
            self.img_metadata[key] = val

    @pyqtSlot(np.ndarray, float)
    def run_experiment(self, img, timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_experiment)

        curr_time = perf_counter()
        self.img_metadata["looptime"] = curr_time - self.last_time
        self.last_time = curr_time

        if self.count >= MAX_FRAMES:
            self.to_intermission()
        else:
            # Record timestamp before running routines
            self.img_metadata["timestamp"] = timestamp
            self.img_metadata["im_counter"] = f"{self.count:0{self.digits}d}"

            t0 = perf_counter()
            self.update_img_count.emit(self.count)
            t1 = perf_counter()
            self._update_metadata_if_verbose("update_img_count", t1 - t0)

            t0 = perf_counter()
            prev_yogo_results: List[
                AsyncInferenceResult
            ] = self.count_parasitemia_routine.send((img, self.count))

            t1 = perf_counter()
            self._update_metadata_if_verbose("count_parasitemia", t1 - t0)

            t0 = perf_counter()
            # we can use this for cell counts in the future, and also density in the now

            for result in prev_yogo_results:
                filtered_prediction = YOGO.filter_res(result.result)

                class_counts = YOGO.class_instance_count(filtered_prediction)
                class_counts = class_counts * YOGO_PERIOD_S * 30
                self.cell_counts += class_counts

                try:
                    self.density_routine.send(filtered_prediction)
                except LowDensity as e:
                    self.logger.warning(f"Cell density is too low.")
                    self.send_pause.emit(
                        "Low cell density",
                        (
                            "Cell density is too low. "
                            "Pausing operation so that more sample can be added without ending the experiment."
                            '\n\nClick "OK" and wait for the next dialog before removing the CAP module.'
                        ),
                    )
                    return

            self.update_cell_count.emit(self.cell_counts)
            t1 = perf_counter()
            self._update_metadata_if_verbose("yogo_result_mgmt", t1 - t0)

            t0 = perf_counter()
            try:
                focus_err = self.PSSAF_routine.send(img)
            except MotorControllerError as e:
                if not SIMULATION:
                    self.logger.error(
                        "Autofocus failed. Can't achieve focus within condenser's depth of field."
                    )
                    self.error.emit(
                        "Autofocus failed",
                        "Unable to achieve desired focus within condenser's depth of field.",
                        False,
                    )
                    return
                else:
                    self.logger.warning(
                        f"Ignoring periodic SSAF exception in simulation mode - {e}"
                    )
                    focus_err = None

                    self.PSSAF_routine = periodicAutofocusWrapper(self.mscope, None)
                    self.PSSAF_routine.send(None)
            t1 = perf_counter()
            self._update_metadata_if_verbose("pssaf", t1 - t0)

            t0 = perf_counter()
            try:
                flowrate = self.flowcontrol_routine.send((img, timestamp))
            except CantReachTargetFlowrate as e:
                if not SIMULATION:
                    self.logger.error(
                        "Flow control failed. Syringe already at max position."
                    )
                    self.error.emit(
                        "Flow control failed",
                        "Unable to achieve desired flowrate with syringe at max position.",
                        False,
                    )
                    return
                else:
                    self.logger.warning(
                        f"Ignoring flowcontrol exception in simulation mode - {e}"
                    )
                    flowrate = None
            t1 = perf_counter()
            self._update_metadata_if_verbose("flowrate_dt", t1 - t0)

            # Update infopanel
            if focus_err != None:
                # TODO change this to non int?
                self.update_focus.emit(int(focus_err))

            if flowrate != None:
                self.update_flowrate.emit(flowrate)

            t1 = perf_counter()
            self._update_metadata_if_verbose("ui_flowrate_focus", t1 - t0)

            t0 = perf_counter()
            # Update remaining metadata
            self.img_metadata["motor_pos"] = self.mscope.motor.getCurrentPosition()
            try:
                pressure, status = self.mscope.pneumatic_module.getPressure()
                (
                    self.img_metadata["pressure_hpa"],
                    self.img_metadata["pressure_status_flag"],
                ) = (pressure, status)
            except PressureSensorStaleValue as e:
                ## TODO???
                self.logger.info(f"Stale pressure sensor value - {e}")

            self.img_metadata[
                "syringe_pos"
            ] = self.mscope.pneumatic_module.getCurrentDutyCycle()
            self.img_metadata["flowrate"] = flowrate
            self.img_metadata["focus_error"] = focus_err

            current_time = perf_counter()
            if current_time - self.TH_time > TH_PERIOD:
                self.TH_time = current_time

                self.img_metadata[
                    "humidity"
                ] = self.mscope.ht_sensor.getRelativeHumidity()
                self.img_metadata[
                    "temperature"
                ] = self.mscope.ht_sensor.getTemperature()
            else:
                self.img_metadata["humidity"] = None
                self.img_metadata["temperature"] = None

            qsize = self.mscope.data_storage.zw.executor._work_queue.qsize()
            self.img_metadata["zarrwriter_qsize"] = qsize

            self.img_metadata["runtime"] = perf_counter() - curr_time

            t1 = perf_counter()
            self._update_metadata_if_verbose("img_metadata", t1 - t0)

            t0 = perf_counter()
            self.mscope.data_storage.writeData(img, self.img_metadata, self.count)
            self.count += 1
            t1 = perf_counter()
            self._update_metadata_if_verbose("datastorage.writeData", t1 - t0)

            if self.running:
                self.img_signal.connect(self.run_experiment)
