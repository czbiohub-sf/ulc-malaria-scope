"""Mid-level/hardware state machine manager

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
from ulc_mm_package.hardware.motorcontroller import InvalidMove, MotorControllerError
from ulc_mm_package.hardware.hardware_constants import TH_PERIOD_NUM
from ulc_mm_package.hardware.pneumatic_module import (
    PressureLeak,
    PressureSensorStaleValue,
    PressureSensorBusy,
)

from ulc_mm_package.image_processing.classic_focus import OOF
from ulc_mm_package.image_processing.focus_metrics import downsample_image
from ulc_mm_package.image_processing.flow_control import CantReachTargetFlowrate
from ulc_mm_package.image_processing.cell_finder import (
    LowDensity,
    NoCellsFound,
)
from ulc_mm_package.image_processing.autobrightness import (
    BrightnessTargetNotAchieved,
    BrightnessCriticallyLow,
    LEDNoPower,
)

from ulc_mm_package.neural_nets.neural_network_constants import IMG_RESIZED_DIMS
from ulc_mm_package.neural_nets.YOGOInference import YOGO, ClassCountResult
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_CLASS_LIST,
    AF_BATCH_SIZE,
)
import ulc_mm_package.neural_nets.utils as nn_utils

from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.QtGUI.gui_constants import (
    TIMEOUT_PERIOD_S,
    ERROR_BEHAVIORS,
    QR,
    COMPLETE_MSG,
    TIMEOUT_MSG,
    PARASITEMIA_VIS_MSG,
)

from ulc_mm_package.scope_constants import (
    DOWNSAMPLE_FACTOR,
    PER_IMAGE_METADATA_KEYS,
    SIMULATION,
    MAX_FRAMES,
    VERBOSE,
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
    FRAME_LOG_INTERVAL,
    PERIODIC_METADATA_KEYS,
)


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
    experiment_done = pyqtSignal(str, str)
    reset_done = pyqtSignal()

    yield_mscope = pyqtSignal(MalariaScope)

    precheck_error = pyqtSignal()
    default_error = pyqtSignal(str, str, int, str)

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

        self.ambient_pressure = None
        self.mscope = None
        self.digits = int(np.log10(MAX_FRAMES - 1)) + 1

        self._set_exp_variables()

        states = [
            {
                "name": "pause",
                "on_enter": [self._send_state, self._track_time, self._start_pause],
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
                "name": "autobrightness_preflow",
                "display_name": "autobrightness (pre-flow)",
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
                "name": "autobrightness_postflow",
                "display_name": "autobrightness (post-flow)",
                "on_enter": [self._send_state, self._start_autobrightness],
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
            trigger="oof_to_motor_sweep",
            source="experiment",
            dest="cellfinder",
            before=[self._track_time, self._oof_handler],
        )
        self.add_transition(
            trigger="skip_flow_control", source="autofocus_preflow", dest="experiment"
        )

    def _set_exp_variables(self):
        self.running = None
        self.lid_opened = None
        self.autofocus_done = False

        self.img_metadata = {key: None for key in PER_IMAGE_METADATA_KEYS}

        self.filtered_focus_err = None
        self.last_img = None  # Needed when initializing class image focus metric during set up steps
        self.classic_focus_routine = None
        self._oof_error = False

        self.flowrate = None
        self.target_flowrate = None

        self.frame_count = 0
        self.raw_cell_count = np.zeros(len(YOGO_CLASS_LIST), dtype=int)

        self.start_time = None
        self.accumulated_time = 0

        self.parasitemia_vis_path = ""

        self.periodic_log_values = {key: None for key in PERIODIC_METADATA_KEYS}

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
            self.update_cell_count.emit(self.raw_cell_count)
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
                + "\n\nPlease contact Biohub."
                f"{', '.join(failed_components).capitalize()}.",
                ERROR_BEHAVIORS.PRECHECK.value,
                QR.NONE.value,
            )
            self.precheck_error.emit()

    def lid_open_pause_handler(self, *args):
        self.lid_opened = True
        self.logger.info("Lid opened.")
        if self.mscope.led._isOn:
            self.lid_open_pause.emit()

    def lid_closed_handler(self, *args):
        self.lid_opened = False

    def set_ambient_pressure(self, ambient_pressure):
        self.ambient_pressure = ambient_pressure

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

    def _track_time(self):
        # Account for case when pause is entered during the initial setup
        if self.start_time is not None:
            self.accumulated_time += perf_counter() - self.start_time
            self.start_time = None

    def _start_pause(self, *args):
        self.running = False

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
            pdiff = self.routines.checkPressureDifference(
                self.mscope, self.ambient_pressure
            )
            self.logger.info(
                f"Pressure check ✅. Ambient absolute pressure: {self.ambient_pressure:.2f} mBar. Gauge pressure = {pdiff:.2f} mBar."
            )
            if self.state == "pressure_check":
                self.next_state()
        except PressureSensorBusy as e:
            self.logger.error(f"Unable to read value from the pressure sensor - {e}")
            # TODO What to do in a case where the sensor is acting funky?
            self.default_error.emit(
                "Calibration failed",
                "Failed to read pressure sensor to perform pressure seal check.",
                ERROR_BEHAVIORS.NO_RELOAD.value,
                QR.NONE.value,
            )
        except PressureLeak as e:
            self.logger.error(f"Pressure leak detected: {e}")
            self.default_error.emit(
                "Calibration failed",
                str(e),
                ERROR_BEHAVIORS.RELOAD.value,
                QR.NONE.value,
            )

    def _start_cellfinder(self, *args):
        self.cellfinder_result = None
        skip_syringe_pull = self._oof_error
        self.cellfinder_routine = self.routines.find_cells_routine(
            self.mscope, skip_syringe_pull=skip_syringe_pull
        )

        self.img_signal.connect(self.run_cellfinder)

    def _end_cellfinder(self, *args):
        if self.cellfinder_result is not None:
            self.update_msg.emit(
                f"Moving motor to focus position at {self.cellfinder_result} steps."
            )
            self.logger.info(f"Moving motor to {self.cellfinder_result}.")

            # Wait for motor to stop moving
            while self.mscope.motor.is_locked():
                sleep(0.1)
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
            if self.classic_focus_routine is None:
                self.classic_focus_routine = self.routines.classic_focus_routine(
                    downsample_image(self.last_img, 10)
                )
            else:
                self.routines.classic_focus._check_and_update_metric(
                    downsample_image(self.last_img, 10)
                )
        except Exception as e:
            self.logger.error(
                f"Iniitalizing ClassicFocus object failed: {e}. Critical error, exiting now."
            )
            raise

    def _start_experiment(self, *args):
        self.periodic_autobrightness_routine = (
            self.routines.periodic_autobrightness_routine(self.mscope)
        )

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
            self.logger.info(f"Net FPS is {self.frame_count/runtime:.1f}")

        self.finishing_experiment.emit(10)

        # the ThreadPoolExecutor work queue may be really big - so as the NCS
        # is chugging along, lets do some work by adding it's results to the
        # prediction handler
        num_images_leftover = self.mscope.cell_diagnosis_model.work_queue_size()
        self.logger.info(
            f"Waiting for {num_images_leftover} images to be processed by the NCS"
        )

        t0 = perf_counter()

        final_yogo_results = self.mscope.cell_diagnosis_model.reset(wait_for_jobs=True)

        self.finishing_experiment.emit(15)

        for result in final_yogo_results:
            self.mscope.predictions_handler.add_yogo_pred(result)

        t1 = perf_counter()

        self.logger.info(
            f"Finished processing {num_images_leftover} images in {t1-t0:.0f} seconds"
        )

        self.finishing_experiment.emit(65)

        self.mscope.reset_for_end_experiment()

        # Turn camera back on
        self.mscope.camera.startAcquisition()

        class_counts_str = ", ".join(
            f"{class_name}={count}"
            for class_name, count in zip(YOGO_CLASS_LIST, self.raw_cell_count)
        )

        self.logger.info(
            f"Finished experiment. "
            f"Processed {self.frame_count} frames. "
            f"Final class counts: {class_counts_str}"
        )
        self.finishing_experiment.emit(100)

    def _start_intermission(self, msg):
        parasitemia_vis_path = self.mscope.data_storage.get_parasitemia_vis_filename()

        if parasitemia_vis_path.exists():
            self.experiment_done.emit(
                msg + PARASITEMIA_VIS_MSG, str(parasitemia_vis_path)
            )
        else:
            self.experiment_done.emit(msg, "")

    @pyqtSlot(np.ndarray, float)
    def run_autobrightness(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        try:
            self.img_signal.disconnect(self.run_autobrightness)
        except TypeError:
            self.logger.warning(
                "run_autobrightness: img_signal already disconnected, no signal/slot changes were made."
            )

        try:
            self.autobrightness_routine.send(img)
        except StopIteration as e:
            self.autobrightness_result = e.value
            self.logger.info(
                f"Autobrightness ✅. Mean pixel val = {self.autobrightness_result:.1f}."
            )
            self.last_img = img
            if self.state in {
                "autobrightness_precells",
                "autobrightness_preflow",
                "autobrightness_postflow",
            }:
                self.next_state()
        except BrightnessTargetNotAchieved as e:
            self.autobrightness_result = e.value
            self.logger.warning(
                f"Autobrightness target not achieved, but still ok. Mean pixel val = {self.autobrightness_result}."
            )
            if self.state in {
                "autobrightness_precells",
                "autobrightness_preflow",
                "autobrightness_postflow",
            }:
                self.next_state()
        except BrightnessCriticallyLow as e:
            self.logger.error(
                f"Autobrightness failed. Mean pixel value = {e.value}.",
            )
            self.default_error.emit(
                "Calibration failed",
                "LED is too dim to run experiment.",
                ERROR_BEHAVIORS.RELOAD.value,
                QR.NONE.value,
            )
        except LEDNoPower as e:
            if not SIMULATION:
                self.logger.error(f"LED initial functionality test did not pass - {e}")
                self.default_error.emit(
                    "Calibration failed",
                    "Did not pass the off/on LED test.",
                    ERROR_BEHAVIORS.NO_RELOAD.value,
                    QR.NONE.value,
                )
            else:
                if self.state in {
                    "autobrightness_precells",
                    "autobrightness_preflow",
                    "autobrightness_postflow",
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

        try:
            self.img_signal.disconnect(self.run_cellfinder)
        except TypeError:
            self.logger.info(
                "run_cellfinder: img_signal already disconnected, no signal/slot changes were made."
            )

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
                ERROR_BEHAVIORS.RELOAD.value,
                QR.NONE.value,
            )
        else:
            if self.running:
                self.img_signal.connect(self.run_cellfinder)

    @pyqtSlot(np.ndarray, float)
    def run_autofocus(self, img, _timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        try:
            self.img_signal.disconnect(self.run_autofocus)
        except TypeError:
            self.logger.info(
                "run_autofocus: img_signal already disconnected, no signal/slot changes were made."
            )

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
                        "Unable to achieve focus because the stage has reached its range of motion limit.",
                        ERROR_BEHAVIORS.RELOAD.value,
                        QR.NONE.value,
                    )
        else:
            self.last_img = img
            self.autofocus_done = False
            if self.state in {"autofocus_preflow", "autofocus_postflow"}:
                if self._oof_error:
                    # Skip fast flow if we're transitioning back to experiment from an OOF error
                    self._oof_error = False
                    self.skip_flow_control()
                else:
                    self.next_state()

    @pyqtSlot(np.ndarray, float)
    def run_fastflow(self, img, timestamp):
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        try:
            self.img_signal.disconnect(self.run_fastflow)
        except TypeError:
            self.logger.info(
                "run_fastflow: img_signal already disconnected, no signal/slot changes were made."
            )

        try:
            img_ds_10x = downsample_image(img, DOWNSAMPLE_FACTOR)
            self.flowrate, syringe_can_move = self.fastflow_routine.send(
                (img_ds_10x, timestamp)
            )

            if self.flowrate is not None:
                self.update_flowrate.emit(self.flowrate)

                if (syringe_can_move is not None) and (not syringe_can_move):
                    # Raise this exception only during the first fast flow set up.
                    # The reason being, later on in the run if we re-enter this state (say due to a focus reset)
                    raise CantReachTargetFlowrate(self.flowrate)
        except StopIteration as e:
            self.fastflow_result = e.value
            curr_pressure_gauge = abs(
                self.mscope.pneumatic_module.getAmbientPressure()
                - self.mscope.pneumatic_module.getPressure()[0]
            )
            self.logger.info(
                f"Fastflow ✅. Flowrate = {self.fastflow_result:.2f} @ gauge pressure: {curr_pressure_gauge:.2f} mBar."
            )
            self.update_flowrate.emit(self.fastflow_result)
            if self.state == "fastflow":
                self.next_state()
        except CantReachTargetFlowrate:
            self.fastflow_result = self.flowrate
            self.logger.error("Fastflow failed. Syringe already at max position.")
            self.update_flowrate.emit(self.fastflow_result)
            self.default_error.emit(
                "Calibration issue",
                "Unable to achieve target flowrate with syringe at max position. Continue running anyway?",
                ERROR_BEHAVIORS.FLOWCONTROL.value,
                QR.NONE.value,
            )
        except Exception as e:
            self.logger.error(f"Unexpected exception in fastflow - {e}")
            self.default_error.emit(
                "Closed loop control failed",
                "Unexpected exception in flow control routine.",
                ERROR_BEHAVIORS.NO_RELOAD.value,
                QR.NONE.value,
            )
        else:
            if self.running:
                self.img_signal.connect(self.run_fastflow)

    def _update_metadata_if_verbose(self, key: str, val: Any):
        if VERBOSE:
            self.img_metadata[key] = val

    def _oof_handler(self):
        self.classic_focus_routine = None
        self.set_period.emit(ACQUISITION_PERIOD)
        self._oof_error = True

    @pyqtSlot(np.ndarray, float)
    def run_experiment(self, img, timestamp) -> None:
        if not self.running:
            self.logger.info("Slot executed after experiment ended.")
            return

        try:
            self.img_signal.disconnect(self.run_experiment)
        except TypeError:
            self.logger.info(
                "run_experiment: img_signal already disconnected, no signal/slot changes were made."
            )

        current_time = perf_counter()
        self.img_metadata["looptime"] = current_time - self.last_time
        self.last_time = current_time

        if self.start_time is None:
            # A race condition has triggered a non-experiment state
            return

        if self.frame_count >= MAX_FRAMES:
            if self.state == "experiment":
                self.update_img_count.emit(self.frame_count)

                self.to_intermission(COMPLETE_MSG)
            return

        if current_time - self.start_time > TIMEOUT_PERIOD_S:
            if self.state == "experiment":
                self.to_intermission(TIMEOUT_MSG)
            return

        # Record timestamp before running routines
        self.img_metadata["timestamp"] = round(timestamp, 2)
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

        # ------------------------------------
        # Get and process YOGO results
        # ------------------------------------
        t0 = perf_counter()
        for result in prev_yogo_results:
            self.mscope.predictions_handler.add_yogo_pred(result)
            self.mscope.predictions_handler.add_raw_pred_to_heatmap(result)

            class_counts = nn_utils.get_class_counts(
                self.mscope.predictions_handler.parsed_tensor
            )

            self.raw_cell_count += class_counts

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

        # ------------------------------------
        # Run periodic singleshot autofocus routine
        # ------------------------------------
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
                    "Autofocus failed. Can't achieve focus within focal range."
                )
                self.default_error.emit(
                    "Closed loop control failed",
                    "Unable to achieve desired focus within focal range.",
                    ERROR_BEHAVIORS.RELOAD.value,
                    QR.NONE.value,
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

        # ------------------------------------
        # Get classic image sharpness metric
        # ------------------------------------
        t0 = perf_counter()
        # Downsample image for use in flowrate + classic image focus metric
        img_ds_10x = downsample_image(img, 10)
        try:
            # Returns the ratio of the current sharpness metric over the best seen
            # so far
            sharpness_ratio_rel_peak = self.classic_focus_routine.send(img_ds_10x)
        except OOF as e:
            self.logger.warning(
                f"Strayed too far away from focus, transitioning to cell-finder. {e}"
            )
            self.oof_to_motor_sweep()
            return

        # ------------------------------------
        # Run flow control routine
        # ------------------------------------
        try:
            self.flowrate, _ = self.flowcontrol_routine.send((img_ds_10x, timestamp))
        except Exception as e:
            self.logger.error(f"Unexpected flow control exception - {e}")
            self.flowrate = -1
            self.flowcontrol_routine = self.routines.flow_control_routine(
                self.mscope, self.target_flowrate
            )

        t1 = perf_counter()
        self._update_metadata_if_verbose("flowrate_dt", t1 - t0)

        # ------------------------------------
        # Run periodic autobrightness routine
        # ------------------------------------
        curr_mean_pixel_val = self.periodic_autobrightness_routine.send(resized_img)

        # ------------------------------------
        # Update remaining metadata in per-image csv and log
        # ------------------------------------
        t0 = perf_counter()
        self.img_metadata["motor_pos"] = self.mscope.motor.getCurrentPosition()
        try:
            pressure, status = self.mscope.pneumatic_module.getPressure()
            self.img_metadata["pressure_hpa"] = (
                round(pressure, 2) if pressure is not None else pressure
            )
        except PressureSensorStaleValue as e:
            ## TODO???
            self.logger.error(f"Stale pressure sensor value - {e}")

        self.img_metadata["led_pwm_val"] = round(self.mscope.led.pwm_duty_cycle, 4)
        self.img_metadata["syringe_pos"] = round(
            self.mscope.pneumatic_module.getCurrentDutyCycle(), 4
        )
        self.img_metadata["flowrate"] = (
            round(self.flowrate, 4) if self.flowrate is not None else self.flowrate
        )
        self.img_metadata["focus_error"] = (
            round(raw_focus_err, 4) if raw_focus_err is not None else raw_focus_err
        )
        self.img_metadata["filtered_focus_error"] = (
            round(filtered_focus_err, 4)
            if filtered_focus_err is not None
            else filtered_focus_err
        )
        self.img_metadata["focus_adjustment"] = focus_adjustment
        self.img_metadata["classic_sharpness_ratio"] = (
            round(sharpness_ratio_rel_peak, 4)
            if sharpness_ratio_rel_peak is not None
            else sharpness_ratio_rel_peak
        )
        self.img_metadata["mean_pixel_val"] = (
            round(curr_mean_pixel_val, 4)
            if curr_mean_pixel_val is not None
            else curr_mean_pixel_val
        )

        if self.frame_count % TH_PERIOD_NUM == 0:
            try:
                (
                    temperature,
                    humidity,
                ) = self.mscope.ht_sensor.get_temp_and_humidity()
                self.img_metadata["humidity"] = round(humidity, 4)
                self.img_metadata["temperature"] = round(temperature, 2)
                self.img_metadata["camera_temperature"] = round(
                    self.mscope.camera._getTemperature(), 2
                )
            except Exception as e:
                # some error has occurred, but the TH sensor isn't critical, so just warn
                # and move on
                self.logger.error(
                    f"exception occurred while retrieving temperature and humidity: {e}"
                )
                self.img_metadata["humidity"] = None
                self.img_metadata["temperature"] = None
        else:
            self.img_metadata["humidity"] = None
            self.img_metadata["temperature"] = None

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

        for key in PERIODIC_METADATA_KEYS:
            val = self.img_metadata.get(key, None)
            if val is not None:
                self.periodic_log_values[key] = val

        if self.frame_count % FRAME_LOG_INTERVAL == 0:
            # Log full periodic metadata
            self.logger.info(
                f"[Frame {self.frame_count}] Full periodic metadata: {self.periodic_log_values}"
            )

        if self.running:
            self.img_signal.connect(self.run_experiment)
