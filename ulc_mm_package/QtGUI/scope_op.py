""" Mid-level/hardware state machine manager

Controls hardware (ie. the Scope) operations.
Manages hardware routines and interactions with Oracle and Acquisition.

"""

import cv2
import logging
import numpy as np

from typing import Any
from time import sleep, perf_counter
from transitions import Machine, State

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ulc_mm_package.hardware.scope import MalariaScope, GPIOEdge

from ulc_mm_package.hardware.scope_routines import Routines

from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.image_processing.classic_focus import OOF
from ulc_mm_package.image_processing.focus_metrics import downsample_image
from ulc_mm_package.scope_constants import (
    PER_IMAGE_METADATA_KEYS,
    SIMULATION,
    MAX_FRAMES,
    VERBOSE,
)

from ulc_mm_package.image_processing.flow_control import (
    CantReachTargetFlowrate,
    LowConfidenceCorrelations,
)
from ulc_mm_package.image_processing.cell_finder import (
    LowDensity,
    NoCellsFound,
)
from ulc_mm_package.image_processing.autobrightness import (
    BrightnessTargetNotAchieved,
    BrightnessCriticallyLow,
    LEDNoPower,
)
from ulc_mm_package.hardware.motorcontroller import InvalidMove, MotorControllerError
from ulc_mm_package.hardware.hardware_constants import TH_PERIOD_NUM
from ulc_mm_package.hardware.pneumatic_module import (
    PressureLeak,
    PressureSensorStaleValue,
    PressureSensorBusy,
)
from ulc_mm_package.neural_nets.neural_network_constants import IMG_RESIZED_DIMS
from ulc_mm_package.neural_nets.YOGOInference import YOGO, ClassCountResult
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_CLASS_LIST,
    AF_BATCH_SIZE,
)

import ulc_mm_package.neural_nets.utils as nn_utils

from ulc_mm_package.QtGUI.gui_constants import (
    TIMEOUT_PERIOD_M,
    TIMEOUT_PERIOD_S,
    ERROR_BEHAVIORS,
)
from ulc_mm_package.scope_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
)
from ulc_mm_package.utilities.statistics_utils import get_all_stats_str

# TODO populate info?


class NamedState(State):
    def __init__(self, *args, **kwargs):
        if "display_name" in kwargs:
            self.display_name = kwargs.pop("display_name")
        elif "name" in kwargs:
            self.display_name = kwargs["name"]
        super().__init__(*args, **kwargs)


class NamedMachine(Machine):
    state_cls = NamedState


class ScopeOp(QObject, NamedMachine):
    setup_done = pyqtSignal()
    experiment_done = pyqtSignal(str)
    reset_done = pyqtSignal()

    yield_mscope = pyqtSignal(MalariaScope)

    precheck_error = pyqtSignal()
    default_error = pyqtSignal(str, str, int)

    reload_pause = pyqtSignal(str, str)
    lid_open_pause = pyqtSignal()

    create_timers = pyqtSignal()
    start_timers = pyqtSignal()
    stop_timers = pyqtSignal()

    set_period = pyqtSignal(float)
    freeze_liveview = pyqtSignal(bool)

    update_runtime = pyqtSignal(float)
    update_img_count = pyqtSignal(int)
    update_cell_count = pyqtSignal(ClassCountResult)
    update_state = pyqtSignal(str)
    update_msg = pyqtSignal(str)

    finishing_experiment = pyqtSignal(int)

    update_flowrate = pyqtSignal(float)
    update_focus = pyqtSignal(float)

    update_thumbnails_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        self.acquisition = Acquisition()
        self.img_signal = self.acquisition.update_scopeop

        self.routines = Routines()

        self.mscope = None
        self.digits = int(np.log10(MAX_FRAMES - 1)) + 1

        self._set_exp_variables()

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
                "display_name": "autobrightness (pre-cells)",
                "on_enter": [self._send_state, self._start_autobrightness],
            },
            {
                "name": "pressure_check",
                "display_name": "pressure check",
                "on_enter": [self._send_state, self._check_pressure_seal],
            },
            {
                "name": "cellfinder",
                "on_enter": [self._send_state, self._start_cellfinder],
                "on_exit": [self._end_cellfinder],
            },
            {
                "name": "autobrightness_postcells",
                "display_name": "autobrightness (post-cells)",
                "on_enter": [self._send_state, self._start_autobrightness],
                "on_exit": [self._init_classic_focus],
            },
            {
                "name": "autofocus_preflow",
                "display_name": "autofocus (pre-flow)",
                "on_enter": [self._send_state, self._start_autofocus],
                "on_exit": [self._init_classic_focus],
            },
            {
                "name": "fastflow",
                "display_name": "flow control",
                "on_enter": [self._send_state, self._start_fastflow],
            },
            {
                "name": "autofocus_postflow",
                "display_name": "autofocus (post-flow)",
                "on_enter": [self._send_state, self._start_autofocus],
                "on_exit": [self._init_classic_focus],
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
                "pressure_check",
            ]
            states = [entry for entry in states if entry["name"] not in skipped_states]

        Machine.__init__(self, states=states, queued=True, initial="standby")
        self.add_ordered_transitions()
        self.add_transition(
            trigger="rerun",
            source=["intermission", "standby"],
            dest="standby",
            before="reset",
        )
        self.add_transition(
            trigger="unpause", source="pause", dest="autobrightness_precells"
        )
        self.add_transition(
            trigger="oof_to_motor_sweep", source="experiment", dest="cellfinder"
        )

    def _set_exp_variables(self):
        self.running = None
        self.lid_opened = None
        self.autofocus_done = False

        self.img_metadata = {key: None for key in PER_IMAGE_METADATA_KEYS}

        self.filtered_focus_err = None

        self.flowrate = None
        self.target_flowrate = None
        self.flowrate_error_raised = False

        self.frame_count = 0
        self.cell_counts = np.zeros(len(YOGO_CLASS_LIST), dtype=int)

        self.start_time = None
        self.accumulated_time = 0

        self.update_img_count.emit(0)
        self.update_msg.emit("Starting new experiment")

    def _freeze_liveview(self):
        self.freeze_liveview.emit(True)

    def _unfreeze_liveview(self):
        self.freeze_liveview.emit(False)

    def _send_state(self, *args):
        state_name = self.get_state(self.state).display_name

        if self.state != "standby":
            self.update_msg.emit(f"{state_name.capitalize()} in progress...")

        self.logger.info(
            f"Changing state to {self.state} (field of view: {self.frame_count}/{MAX_FRAMES})."
        )
        self.update_state.emit(state_name)

    def _get_experiment_runtime(self) -> float:
        if self.start_time is None:
            return self.accumulated_time
        else:
            return self.accumulated_time + perf_counter() - self.start_time

    def update_infopanel(self):
        if self.state == "experiment":
            self.update_cell_count.emit(self.cell_counts)
            self.update_runtime.emit(self._get_experiment_runtime())
            if self.flowrate is not None:
                self.update_flowrate.emit(self.flowrate)
            if self.filtered_focus_err is not None:
                self.update_focus.emit(self.filtered_focus_err)

    def update_thumbnails(self):
        # Update thumbnails
        if self.state == "experiment":
            self.update_thumbnails_signal.emit(
                (
                    self.mscope.predictions_handler.get_max_conf_thumbnails(
                        self.mscope.data_storage.zw.array
                    ),
                    self.mscope.predictions_handler.get_min_conf_thumbnails(
                        self.mscope.data_storage.zw.array
                    ),
                )
            )

    def setup(self):
        self.create_timers.emit()

        self.mscope = MalariaScope()

        self.yield_mscope.emit(self.mscope)
        if not SIMULATION:
            self.lid_opened = self.mscope.read_lim_sw()
        else:
            self.lid_opened = False
        self.mscope.set_gpio_callback(self.lid_open_pause_handler)
        self.mscope.set_gpio_callback(
            self.lid_closed_handler, edge=GPIOEdge.FALLING_EDGE
        )
        component_status = self.mscope.getComponentStatus()

        if all([status is True for status in component_status.values()]):
            self.setup_done.emit()
        else:
            failed_components = [
                comp.name
                for comp in component_status
                if component_status.get(comp) is False
            ]
            self.logger.error(
                "Hardware pre-check failed: "
                "The following component(s) could not be instantiated: "
                f"{', '.join(failed_components).capitalize()}."
            )
            self.default_error.emit(
                "Hardware pre-check failed",
                "The following component(s) could not be instantiated: "
                f"{', '.join(failed_components).capitalize()}.",
                ERROR_BEHAVIORS.PRECHECK.value,
            )
            self.precheck_error.emit()

    def lid_open_pause_handler(self, *args):
        self.lid_opened = True
        if self.mscope.led._isOn:
            self.lid_open_pause.emit()

    def lid_closed_handler(self, *args):
        self.lid_opened = False

    def start(self):
        self.running = True
        self.start_timers.emit()
        if self.state == "standby":
            self.next_state()

    def reset(self):
        # Reset variables
        self._set_exp_variables()

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

    def _start_pause(self, *args):
        self.running = False
        self.flowrate_error_raised = False

        # Account for case when pause is entered during the initial setup
        if self.start_time is not None:
            self.accumulated_time += perf_counter() - self.start_time
            self.start_time = None

        try:
            self.img_signal.disconnect()
        except TypeError:
            self.logger.info(
                "Since img_signal is already disconnected, no signal/slot changes were made."
            )

        self.mscope.reset_pneumatic_and_led_and_flow_control()

    def _end_pause(self, *args):
        self.set_period.emit(ACQUISITION_PERIOD)
        self.mscope.led.turnOn()

        self.running = True

    def _start_autobrightness(self, *args):
        self.autobrightness_result = None
        self.autobrightness_routine = self.routines.autobrightnessRoutine(self.mscope)

        self.img_signal.connect(self.run_autobrightness)

    def _check_pressure_seal(self, *args):
        # Check that the pressure seal is good (i.e there is a sufficient pressure delta)
        try:
            pdiff = self.routines.checkPressureDifference(self.mscope)
            self.logger.info(
                f"Passed pressure check. Pressure difference = {pdiff} hPa."
            )
            if self.state == "pressure_check":
                self.next_state()
        except PressureSensorBusy as e:
            self.logger.error(f"Unable to read value from the pressure sensor - {e}")
            # TODO What to do in a case where the sensor is acting funky?
            self.default_error.emit(
                "Calibration failed",
                "Failed to read pressure sensor to perform pressure seal check.",
                ERROR_BEHAVIORS.DEFAULT.value,
            )
        except PressureLeak as e:
            self.logger.error(f"Improper seal / pressure leak detected - {e}")
            # TODO provide instructions for dealing with pressure leak?
            self.default_error.emit(
                "Calibration failed",
                "Improper seal / pressure leak detected.",
                ERROR_BEHAVIORS.DEFAULT.value,
            )

    def _start_cellfinder(self, *args):
        self.cellfinder_result = None
        self.cellfinder_routine = self.routines.find_cells_routine(self.mscope)

        self.img_signal.connect(self.run_cellfinder)

    def _end_cellfinder(self, *args):
        if self.cellfinder_result is not None:
            self.update_msg.emit(
                f"Moving motor to focus position at {self.cellfinder_result} steps."
            )
            self.logger.info(f"Moving motor to {self.cellfinder_result}.")
            self.mscope.motor.move_abs(self.cellfinder_result)

    def _start_autofocus(self, *args):
        self.autofocus_batch = []
        self.autofocus_results = [None, None]
        self.img_signal.connect(self.run_autofocus)

    def _start_fastflow(self, *args):
        if SIMULATION:
            self.logger.info(f"Skipping {self.state} state in simulation mode.")
            sleep(1)
            if self.state == "fastflow":
                self.next_state()
            return

        self.fastflow_result = None
        self.fastflow_routine = self.routines.flow_control_routine(
            self.mscope,
            target_flowrate=self.target_flowrate,
            fast_flow=True,
        )

        self.img_signal.connect(self.run_fastflow)

    def _init_classic_focus(self, *args):
        try:
            if not hasattr(self, "classic_focus_routine"):
                self.classic_focus_routine = self.routines.classic_focus_routine(
                    downsample_image(self.last_img, 10)
                )
            else:
                self.routines.classic_focus._check_and_update_metric(downsample_image(self.last_img, 10))
        except Exception as e:
            self.logger.error(
                f"Iniitalizing ClassicFocus object failed: {e}. Critical error, exiting now."
            )
            raise

    def _start_experiment(self, *args):
        self.PSSAF_routine = self.routines.periodicAutofocusWrapper(self.mscope)

        self.flowcontrol_routine = self.routines.flow_control_routine(
            self.mscope,
            self.target_flowrate,
            fast_flow=False,
        )

        self.density_routine = self.routines.cell_density_routine()

        self.set_period.emit(LIVEVIEW_PERIOD)

        self.start_time = perf_counter()
        self.last_time = perf_counter()

        self.img_signal.connect(self.run_experiment)

    def _end_experiment(self, *args):
        self.shutoff()

        self.finishing_experiment.emit(5)

        # Turn off camera
        self.mscope.camera.stopAcquisition()

        runtime = self._get_experiment_runtime()
        if runtime != 0:
            self.logger.info(f"Net FPS is {self.frame_count/runtime}")

        self.finishing_experiment.emit(10)

        def _save_yogo_results():
            for result in self.mscope.cell_diagnosis_model.get_asyn_results():
                self.mscope.predictions_handler.add_yogo_pred(result)

        self.finishing_experiment.emit(15)

        # the ThreadPoolExecutor work queue may be really big - so as the NCS
        # is chugging along, lets do some work by adding it's results to the
        # prediction handler
        num_images_leftover = self.mscope.cell_diagnosis_model.work_queue_size()
        self.logger.info(
            f"Waiting for {num_images_leftover} images to be processed by the NCS"
        )

        t0 = perf_counter()

        while self.mscope.cell_diagnosis_model.work_queue_size() > 0:
            _save_yogo_results()

        self.finishing_experiment.emit(20)

        # once the ThreadPoolExecutor work queue is done, the NCS is still
        # processing images (up to 4 images). Lets wait for them, and then
        # process them in the same way.
        self.mscope.cell_diagnosis_model.wait_all()
        _save_yogo_results()

        t1 = perf_counter()

        self.logger.info(
            f"Finished processing {num_images_leftover} images in {t1-t0:.0f} seconds"
        )

        self.finishing_experiment.emit(25)

        pred_counter = self.mscope.predictions_handler.new_pred_pointer
        if pred_counter != 0:
            nonzero_preds = (
                self.mscope.predictions_handler.get_prediction_tensors()
            )  # (8+NUM_CLASSES) x N

            class_counts = nn_utils.get_class_counts(nonzero_preds)
            sorted_confidences = (
                nn_utils.get_all_argmax_class_confidences_for_all_classes(nonzero_preds)
            )
            unsorted_confidences = nn_utils.get_all_confs_for_all_classes(nonzero_preds)

            stats_string = get_all_stats_str(
                class_counts, unsorted_confidences, sorted_confidences
            )
            self.logger.info(stats_string)

        self.finishing_experiment.emit(90)

        self.mscope.reset_for_end_experiment()

        # Turn camera back on
        self.mscope.camera.startAcquisition()

        self.finishing_experiment.emit(100)

    def _start_intermission(self, msg):
        self.experiment_done.emit(msg)

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
            self.last_img = img
            if self.state in {"autobrightness_precells", "autobrightness_postcells"}:
                self.next_state()
        except BrightnessTargetNotAchieved as e:
            self.autobrightness_result = e.value
            self.logger.warning(
                f"Autobrightness target not achieved, but still ok. Mean pixel val = {self.autobrightness_result}."
            )
            if self.state in {"autobrightness_precells", "autobrightness_postcells"}:
                self.next_state()
        except BrightnessCriticallyLow as e:
            self.logger.error(
                f"Autobrightness failed. Mean pixel value = {e.value}.",
            )
            self.default_error.emit(
                "Autobrightness failed",
                "LED is too dim to run experiment.",
                ERROR_BEHAVIORS.DEFAULT.value,
            )
        except LEDNoPower as e:
            if not SIMULATION:
                self.logger.error(f"LED initial functionality test did not pass - {e}")
                self.default_error.emit(
                    "LED failure",
                    "The off/on LED test failed.",
                    ERROR_BEHAVIORS.DEFAULT.value,
                )
            else:
                if self.state in {
                    "autobrightness_precells",
                    "autobrightness_postcells",
                }:
                    self.next_state()
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
            if self.state == "cellfinder":
                self.next_state()
        except NoCellsFound:
            self.logger.error("Cellfinder failed. No cells found.")
            self.default_error.emit(
                "Calibration failed",
                "No cells found.",
                ERROR_BEHAVIORS.DEFAULT.value,
            )
        else:
            if self.running:
                self.img_signal.connect(self.run_cellfinder)

    @pyqtSlot(np.ndarray, float)
    def run_autofocus(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_autofocus)

        if not self.autofocus_done:
            if len(self.autofocus_batch) < AF_BATCH_SIZE:
                resized_img = cv2.resize(
                    img, IMG_RESIZED_DIMS, interpolation=cv2.INTER_CUBIC
                )
                self.autofocus_batch.append(resized_img)

                if self.running:
                    self.img_signal.connect(self.run_autofocus)
            else:
                try:
                    if self.autofocus_results[0] is None:
                        self.autofocus_results[
                            0
                        ] = self.routines.singleShotAutofocusRoutine(
                            self.mscope, self.autofocus_batch
                        )
                        self.logger.info(
                            f"First autofocus batch complete. Calculated focus error = {self.autofocus_results[0]} steps."
                        )
                        self.autofocus_batch = []

                        # Wait for motor to stop moving
                        while self.mscope.motor.is_locked():
                            sleep(0.1)

                        # Extra delay, to prevent any jitter from motor motion
                        sleep(0.5)

                        if self.running:
                            self.img_signal.connect(self.run_autofocus)
                    else:
                        self.autofocus_results[
                            1
                        ] = self.routines.singleShotAutofocusRoutine(
                            self.mscope, self.autofocus_batch
                        )
                        self.logger.info(
                            f"Second autofocus batch complete. Calculated focus error = {self.autofocus_results[1]} steps."
                        )
                        self.autofocus_batch = []

                        self.autofocus_done = True
                        if self.running:
                            self.img_signal.connect(self.run_autofocus)

                except InvalidMove:
                    self.logger.error(
                        "Autofocus failed. Can't achieve focus because the stage has reached its range of motion limit."
                    )
                    self.default_error.emit(
                        "Calibration failed",
                        "Unable to achieve focus because the stage has reached its range of motion limit..",
                        ERROR_BEHAVIORS.DEFAULT.value,
                    )
        else:
            self.last_img = img
            self.autofocus_done = False
            if self.state in {"autofocus_preflow", "autofocus_postflow"}:
                self.next_state()

    @pyqtSlot(np.ndarray, float)
    def run_fastflow(self, img, timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_fastflow)

        try:
            self.flowrate = self.fastflow_routine.send((img, timestamp))

            if self.flowrate is not None:
                self.update_flowrate.emit(self.flowrate)
        except CantReachTargetFlowrate as e:
            self.fastflow_result = e.flowrate
            self.logger.error("Fastflow failed. Syringe already at max position.")
            self.default_error.emit(
                "Calibration issue",
                "Unable to achieve target flowrate with syringe at max position. Continue running anyway?",
                ERROR_BEHAVIORS.FLOWCONTROL.value,
            )
            self.update_flowrate.emit(self.fastflow_result)
        except LowConfidenceCorrelations:
            self.fastflow_result = -1
            self.logger.error(
                "Fastflow failed. Too many recent low confidence xcorr calculations."
            )
            self.default_error.emit(
                "Calibration failed - flowrate calculation errors",
                (
                    "Flowrate ramp: The flow control system returned too many 'low confidence' measurements. "
                    "You can continue with this run if the flow looks okay to you, "
                    "or restart this run with the same flow cell, or discard this flow cell and use a new one with fresh sample.\n"
                    "Continue running anyway?"
                ),
                ERROR_BEHAVIORS.FLOWCONTROL.value,
            )
        except StopIteration as e:
            self.fastflow_result = e.value
            self.logger.info(f"Fastflow successful. Flowrate = {self.fastflow_result}.")
            self.update_flowrate.emit(self.fastflow_result)
            if self.state == "fastflow":
                self.next_state()
        else:
            if self.running:
                self.img_signal.connect(self.run_fastflow)

    def _update_metadata_if_verbose(self, key: str, val: Any):
        if VERBOSE:
            self.img_metadata[key] = val

    @pyqtSlot(np.ndarray, float)
    def run_experiment(self, img, timestamp) -> None:
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        self.img_signal.disconnect(self.run_experiment)

        current_time = perf_counter()
        self.img_metadata["looptime"] = current_time - self.last_time
        self.last_time = current_time

        if self.start_time is None:
            # A race condition has triggered a non-experiment state
            return

        if self.frame_count >= MAX_FRAMES:
            if self.state == "experiment":
                self.to_intermission(
                    "Ending experiment since data collection is complete."
                )
            return

        if current_time - self.start_time > TIMEOUT_PERIOD_S:
            if self.state == "experiment":
                self.to_intermission(
                    f"Ending experiment since {TIMEOUT_PERIOD_M} minute timeout was reached."
                )
            return

        # Record timestamp before running routines
        self.img_metadata["timestamp"] = timestamp
        self.img_metadata["im_counter"] = f"{self.frame_count:0{self.digits}d}"

        t0 = perf_counter()
        self.update_img_count.emit(self.frame_count)
        t1 = perf_counter()
        self._update_metadata_if_verbose("update_img_count", t1 - t0)

        t0 = perf_counter()
        prev_yogo_results = self.routines.count_parasitemia(
            self.mscope, YOGO.crop_img(img), self.frame_count
        )
        t1 = perf_counter()

        self._update_metadata_if_verbose("count_parasitemia", t1 - t0)

        self._update_metadata_if_verbose(
            "yogo_qsize",
            self.mscope.cell_diagnosis_model.work_queue_size(),
        )

        t0 = perf_counter()
        for result in prev_yogo_results:
            self.mscope.predictions_handler.add_yogo_pred(result)
            self.mscope.predictions_handler.add_raw_pred_to_heatmap(result)

            class_counts = nn_utils.get_class_counts(
                self.mscope.predictions_handler.parsed_tensor
            )

            self.cell_counts += class_counts

            try:
                self.density_routine.send(class_counts)
            except LowDensity:
                self.logger.warning("Cell density is too low.")
                self.reload_pause.emit(
                    "Low cell density",
                    (
                        "Cell density is too low. "
                        "Pausing operation so that more sample can be added without ending the experiment."
                        '\n\nClick "OK" and wait for the next dialog before removing the CAP module.'
                    ),
                )
                return

        t1 = perf_counter()
        self._update_metadata_if_verbose("yogo_result_mgmt", t1 - t0)

        t0 = perf_counter()
        resized_img = cv2.resize(img, IMG_RESIZED_DIMS, interpolation=cv2.INTER_CUBIC)
        try:
            (
                raw_focus_err,
                filtered_focus_err,
                focus_adjustment,
            ) = self.PSSAF_routine.send(resized_img)
        except MotorControllerError as e:
            if not SIMULATION:
                self.logger.error(
                    "Autofocus failed. Can't achieve focus within condenser's depth of field."
                )
                self.default_error.emit(
                    "Autofocus failed",
                    "Unable to achieve desired focus within condenser's depth of field.",
                    ERROR_BEHAVIORS.DEFAULT.value,
                )
                return
            else:
                self.logger.warning(
                    f"Ignoring periodic SSAF exception in simulation mode - {e}"
                )
                raw_focus_err = None

                self.PSSAF_routine = self.routines.periodicAutofocusWrapper(self.mscope)

        t1 = perf_counter()
        self._update_metadata_if_verbose("pssaf", t1 - t0)

        if filtered_focus_err is not None:
            self.filtered_focus_err = filtered_focus_err

        t0 = perf_counter()

        # Downsample image for use in flowrate + classic image focus metric
        img_ds_10x = downsample_image(img, 10)
        try:
            self.classic_focus_routine.send(img_ds_10x)
        except OOF:
            self.logger.warning(
                "Strayed too far away from focus, transitioning to cell-finder."
            )
            self.oof_to_motor_sweep()
        try:
            if not self.flowrate_error_raised:
                self.flowrate = self.flowcontrol_routine.send((img_ds_10x, timestamp))
        except CantReachTargetFlowrate as e:
            self.flowrate_error_raised = True
            self.logger.warning(
                f"Ignoring flowcontrol exception and attempting to maintain flowrate - {e}"
            )
            self.flowrate = -1
            self.flowcontrol_routine = self.routines.flow_control_routine(
                self.mscope, self.target_flowrate
            )
        except LowConfidenceCorrelations as e:
            self.flowrate_error_raised = True
            self.logger.warning(
                f"Ignoring flowcontrol exception and attempting to maintain flowrate - {e}"
            )
            self.flowrate = -1
            self.flowcontrol_routine = self.routines.flow_control_routine(
                self.mscope, self.target_flowrate
            )

        t1 = perf_counter()
        self._update_metadata_if_verbose("flowrate_dt", t1 - t0)

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

        self.img_metadata["led_pwm_val"] = self.mscope.led.pwm_duty_cycle
        self.img_metadata[
            "syringe_pos"
        ] = self.mscope.pneumatic_module.getCurrentDutyCycle()
        self.img_metadata["flowrate"] = self.flowrate
        self.img_metadata["cell_count_cumulative"] = self.cell_counts[0]
        self.img_metadata["focus_error"] = raw_focus_err
        self.img_metadata["filtered_focus_error"] = filtered_focus_err
        self.img_metadata["focus_adjustment"] = focus_adjustment

        if self.frame_count % TH_PERIOD_NUM == 0:
            try:
                (
                    temperature,
                    humidity,
                ) = self.mscope.ht_sensor.get_temp_and_humidity()
                self.img_metadata["humidity"] = humidity
                self.img_metadata["temperature"] = temperature
                self.img_metadata[
                    "camera_temperature"
                ] = self.mscope.camera._getTemperature()
            except Exception as e:
                # some error has occurred, but the TH sensor isn't critical, so just warn
                # and move on
                self.logger.warning(
                    f"exception occurred while retrieving temperature and humidity: {e}"
                )
                self.img_metadata["humidity"] = None
                self.img_metadata["temperature"] = None
                self.img_metadata["camera_temperature"] = None
        else:
            self.img_metadata["humidity"] = None
            self.img_metadata["temperature"] = None
            self.img_metadata["camera_temperature"] = None

        zarr_qsize = self.mscope.data_storage.zw.executor._work_queue.qsize()
        self.img_metadata["zarrwriter_qsize"] = zarr_qsize

        ssaf_qsize = self.mscope.autofocus_model.work_queue_size()
        self._update_metadata_if_verbose("ssaf_qsize", ssaf_qsize)

        self.img_metadata["runtime"] = perf_counter() - current_time

        t1 = perf_counter()
        self._update_metadata_if_verbose("img_metadata", t1 - t0)

        t0 = perf_counter()
        self.mscope.data_storage.writeData(img, self.img_metadata, self.frame_count)
        self.frame_count += 1
        t1 = perf_counter()
        self._update_metadata_if_verbose("datastorage.writeData", t1 - t0)

        if self.running:
            self.img_signal.connect(self.run_experiment)
