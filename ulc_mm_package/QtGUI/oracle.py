""" High-level state machine manager.

The Oracle sees all and knows all.
It owns all GUI windows, threads, and worker objects (ScopeOp and Acquisition).

"""

import os
import sys
import socket
import enum
import logging
import subprocess

from os import (
    listdir,
    mkdir,
    path,
)
from transitions import Machine
from transitions.core import MachineError
from time import sleep
from logging.config import fileConfig
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QLabel,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap

from ulc_mm_package.scope_constants import (
    LOCKFILE,
    EXPERIMENT_METADATA_KEYS,
    PER_IMAGE_METADATA_KEYS,
    CAMERA_SELECTION,
    SSD_DIR,
    VERBOSE,
    SIMULATION,
    SSD_NAME,
    RESEARCH_USE_ONLY,
)
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.data_storage import DataStorage
from ulc_mm_package.image_processing.processing_constants import (
    TOP_PERC_TARGET_VAL,
)
from ulc_mm_package.QtGUI.gui_constants import (
    NO_PAUSE_STATES,
    ICON_PATH,
    ERROR_BEHAVIORS,
    BLANK_INFOPANEL_VAL,
    CLINICAL_SAMPLE,
)
from ulc_mm_package.neural_nets.neural_network_constants import (
    AUTOFOCUS_MODEL_DIR,
    YOGO_MODEL_DIR,
)
from ulc_mm_package.utilities.email_utils import send_ngrok_email, EmailError
from ulc_mm_package.utilities.ngrok_utils import make_tcp_tunnel, NgrokError

from ulc_mm_package.QtGUI.scope_op import ScopeOp
from ulc_mm_package.QtGUI.form_gui import FormGUI
from ulc_mm_package.QtGUI.liveview_gui import LiveviewGUI

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ERROR_MSG = '\n\nClick "OK" to end this run.'

_IMAGE_INSERT_PATH = "gui_images/insert_infographic.png"
_IMAGE_REMOVE_PATH = "gui_images/remove_infographic.png"
_IMAGE_RELOAD_PATH = "gui_images/remove_infographic.png"


class Buttons(enum.Enum):
    OK = QMessageBox.Ok
    CANCEL = QMessageBox.Cancel | QMessageBox.Ok
    YN = QMessageBox.No | QMessageBox.Yes


class ShutoffApplication(QApplication):
    shutoff = pyqtSignal()

    def connect_signal(self, func):
        self.shutoff.connect(func)


class NoCloseMessageBox(QMessageBox):
    def __init__(self):
        super().__init__()

        # Disable [x] button (this doesn't work on all raspian images!)
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

    # In case the [x] button can't be disabled, this prevents the window from closing when it's clicked
    def closeEvent(self, event):
        if event.spontaneous():
            event.ignore()
        else:
            event.accept()


class Oracle(Machine):
    def __init__(self):
        self.shutoff_done = False

        # Save startup datetime
        self.datetime_str = datetime.now().strftime(DATETIME_FORMAT)

        # Instantiate message dialog
        self.message_window = NoCloseMessageBox()

        # Setup SSD
        self._init_ssd()

        # Setup directory for logs
        log_dir = path.join(self.ext_dir, "logs")
        if not path.isdir(log_dir):
            mkdir(log_dir)

        # Setup logger
        fileConfig(
            fname="../logger.config",
            defaults={
                "filename": path.join(log_dir, f"{self.datetime_str}.log"),
                "fileHandlerLevel": "DEBUG" if VERBOSE else "INFO",
            },
        )
        self.logger = logging.root
        self.logger.info("STARTING ORACLE.")

        # Instantiate GUI windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()

        # Check lock and tcp tunnel
        self._init_tcp()
        self._check_lock()

        # Instantiate and configure Oracle elements
        self._set_variables()
        self._init_threads()
        self._init_states()
        self._init_sigslots()

        # Trigger first transition
        self.next_state()

    def _init_tcp(self):
        try:
            tcp_addr = make_tcp_tunnel()
            self.logger.info(f"SSH address is {tcp_addr}.")
            self.liveview_window.update_tcp(tcp_addr)
            send_ngrok_email()
        except NgrokError as e:
            message_result = self.display_message(
                QMessageBox.Icon.Warning,
                "SSH tunnel failed",
                (
                    "Could not create SSH tunnel, so the scope cannot be accessed remotely. "
                    "The SSH tunnel is only recreated when the scope is rebooted."
                    '\n\nClick "OK" to continue running without SSH or click "Cancel" to exit.'
                ),
                buttons=Buttons.CANCEL,
            )
            if message_result == QMessageBox.Cancel:
                self.logger.warning(
                    f"Terminating run because SSH address could not be found - {e}"
                )
                sys.exit(1)
            self.logger.warning(f"SSH address could not be found - {e}")
            self.liveview_window.update_tcp("unavailable")
        except EmailError as e:
            self.display_message(
                QMessageBox.Icon.Warning,
                "SSH email failed",
                (
                    "Could not automatically email SSH tunnel address. "
                    "If SSH is needed, please use the address printed in the liveviewer or terminal. "
                    '\n\nClick "OK" to continue running.'
                ),
                buttons=Buttons.OK,
            )
            self.logger.warning(f"SSH address could not be emailed - {e}")
        except Exception as e:
            self.logger.warning(f"Unexpected error while setting up TCP: {e}")

    def _check_lock(self):
        if path.isfile(LOCKFILE):
            message_result = self.display_message(
                QMessageBox.Icon.Information,
                "Scope in use",
                "The scope is locked because another run is in progress. "
                'Override lock and run anyways?\n\nClick "No" to end run (recommended). '
                'Click "Yes" to override lock and run anyways, at your own risk.',
                buttons=Buttons.YN,
            )
            if message_result == QMessageBox.No:
                self.logger.warning(
                    f"Terminating run because scope is locked when lockfile ({LOCKFILE}) exists."
                )
                sys.exit(1)
            else:
                self.logger.warning(
                    f"Overriding lock and running even though lockfile ({LOCKFILE}) exists."
                )
        else:
            open(LOCKFILE, "w")

    def _set_variables(self):
        # Instantiate metadata dicts
        self.form_metadata = None
        self.experiment_metadata = {key: None for key in EXPERIMENT_METADATA_KEYS}

        self.liveview_window.set_infopanel_vals()

        # Lid handler
        self.lid_handler_enabled = False

    def _init_threads(self):
        # Instantiate scope operator and thread
        self.scopeop = ScopeOp()
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Instantiate camera acquisition and thread
        self.acquisition = self.scopeop.acquisition
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)

        self.scopeop_thread.started.connect(self.scopeop.setup)

    def _init_states(self):
        states = [
            {
                "name": "standby",
            },
            {
                "name": "setup",
                "on_enter": [self._start_setup],
                "on_exit": [self._end_setup],
            },
            {
                "name": "form",
                "on_enter": [self._start_form],
                "on_exit": [self._end_form],
            },
            {
                "name": "liveview",
                "on_enter": [self._start_liveview],
                "on_exit": [self._end_liveview],
            },
            {
                "name": "intermission",
                "on_enter": [self._start_intermission],
            },
        ]

        super().__init__(self, states=states, queued=True, initial="standby")
        self.add_ordered_transitions()
        self.add_transition(
            trigger="rerun",
            source="intermission",
            dest="form",
            before=self._set_variables,
        )

    def _init_sigslots(self):
        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.form_exit_handler)
        self.form_window.close_event.connect(self.close_handler)

        # Connect liveview buttons
        self.liveview_window.pause_btn.clicked.connect(self.general_pause_handler)
        self.liveview_window.exit_btn.clicked.connect(self.liveview_exit_handler)
        self.liveview_window.close_event.connect(self.close_handler)

        # Thumbnail display signals
        self.liveview_window.refresh_thumbnails.clicked.connect(
            self.scopeop.update_thumbnails
        )
        self.scopeop.update_thumbnails_signal.connect(
            self.liveview_window.update_thumbnails
        )

        # Connect scopeop signals and slots
        self.scopeop.setup_done.connect(self.to_form)
        self.scopeop.experiment_done.connect(self.to_intermission)
        self.scopeop.reset_done.connect(self.rerun)

        self.scopeop.yield_mscope.connect(self.acquisition.get_mscope)

        self.scopeop.precheck_error.connect(self.shutoff)
        self.scopeop.default_error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.reload_pause.connect(self.reload_pause_handler)
        self.scopeop.lid_open_pause.connect(self.lid_open_pause_handler)

        self.scopeop.create_timers.connect(self.acquisition.create_timers)
        self.scopeop.start_timers.connect(self.acquisition.start_timers)
        self.scopeop.stop_timers.connect(self.acquisition.stop_timers)

        self.scopeop.update_runtime.connect(self.liveview_window.update_runtime)
        self.scopeop.update_img_count.connect(self.liveview_window.update_img_count)
        self.scopeop.update_cell_count.connect(self.liveview_window.update_cell_count)
        self.scopeop.update_state.connect(self.liveview_window.update_state)
        self.scopeop.update_msg.connect(self.liveview_window.update_msg)

        self.scopeop.update_flowrate.connect(self.liveview_window.update_flowrate)
        self.scopeop.update_focus.connect(self.liveview_window.update_focus)

        self.scopeop.finishing_experiment.connect(
            self.liveview_window.hide_state_label_show_progress_bar
        )

        # Connect acquisition signals and slots
        self.acquisition.update_liveview.connect(self.liveview_window.update_img)
        self.acquisition.update_infopanel.connect(self.scopeop.update_infopanel)

    def _init_ssd(self):
        samsung_ext_dir = path.join(SSD_DIR, SSD_NAME)
        if path.exists(samsung_ext_dir):
            self.ext_dir = samsung_ext_dir + "/"
        else:
            print(
                f"Could not find '{SSD_NAME}' in {SSD_DIR}. Searching for other folders in this directory."
            )
            try:
                self.ext_dir = SSD_DIR + listdir(SSD_DIR)[0] + "/"
            except (FileNotFoundError, IndexError):
                print(
                    f"Could not find any folders within {SSD_DIR}. Check that the SSD is plugged in."
                )
                self.display_message(
                    QMessageBox.Icon.Critical,
                    "SSD not found",
                    f"Could not find any folders within {SSD_DIR}. Check that the SSD is plugged in."
                    + _ERROR_MSG,
                    buttons=Buttons.OK,
                )
                sys.exit(1)
        print(f"Saving data to {self.ext_dir}")

        if not DataStorage.is_there_sufficient_storage(self.ext_dir):
            self.ssd_full_msg_and_exit()
            sys.exit(1)

    def ssd_full_msg_and_exit(self):
        print(
            "The SSD is full. Please eject and then replace the SSD with a new one. Thank you!"
        )
        self.display_message(
            QMessageBox.Icon.Critical,
            "SSD is full",
            "The SSD is full. Data cannot be saved if the SSD is full. Please eject and then replace the SSD with a new one. Thank you!"
            + _ERROR_MSG,
            buttons=Buttons.OK,
        )

    def reload_pause_handler(self, title, message):
        if self.scopeop.state not in NO_PAUSE_STATES:
            self.scopeop.to_pause()

        self.general_pause_handler(
            icon=QMessageBox.Icon.Warning,
            title=title,
            message=message,
            buttons=Buttons.OK,
        )

    def lid_open_pause_handler(self):
        if self.scopeop.state not in NO_PAUSE_STATES:
            self.scopeop.to_pause()
            self.unpause()

    def general_pause_handler(
        self,
        icon=QMessageBox.Icon.Information,
        title="Pause run?",
        message=(
            "While paused, you can add more sample to the flow cell. "
            "After pausing, the scope will restart the calibration steps."
            '\n\nClick "OK" to pause this run and wait for the next dialog before removing the CAP module.'
        ),
        buttons=Buttons.CANCEL,
    ):
        message_result = self.display_message(
            icon,
            title,
            message,
            buttons=buttons,
        )
        if message_result == QMessageBox.Ok:
            if self.scopeop.state not in NO_PAUSE_STATES:
                self.scopeop.to_pause()
        else:
            return

        sleep(2)
        self.display_message(
            QMessageBox.Icon.Information,
            "Paused run - reload sample",
            (
                "The CAP module can now be removed."
                "\n\nPlease empty both reservoirs and reload 12 uL of fresh "
                "diluted blood (from the same participant) into the sample reservoir. Make sure to close the lid after."
                '\n\nAfter reloading the reservoir and closing the lid, click "OK" to resume this run.'
            ),
            buttons=Buttons.OK,
            image=_IMAGE_RELOAD_PATH,
        )
        self.close_lid_display_message()
        self.unpause()

    def unpause(self):
        self.close_lid_display_message()
        self.liveview_window.update_flowrate(BLANK_INFOPANEL_VAL)
        self.liveview_window.update_focus(BLANK_INFOPANEL_VAL)

        try:
            self.scopeop.unpause()
        except MachineError:
            self.scopeop.to_pause()
            self.scopeop.unpause()

    def close_handler(self):
        self.display_message(
            QMessageBox.Icon.Warning,
            "Improper exit",
            (
                'Please close this window using the "Exit" button instead. '
                "This ensures proper shutoff of the scope hardware. "
            ),
            buttons=Buttons.OK,
        )

    def form_exit_handler(self):
        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "End experiment?",
            'Click "OK" to end the experiment and shutoff the scope.',
            buttons=Buttons.CANCEL,
        )
        if message_result == QMessageBox.Ok:
            self.shutoff()

    def liveview_exit_handler(self):
        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "End run?",
            'Click "OK" to end this run.',
            buttons=Buttons.CANCEL,
        )
        if message_result == QMessageBox.Ok:
            self.lid_handler_enabled = False
            self.scopeop.to_intermission("Ending experiment due to user prompt.")

    def error_handler(self, title, text, behavior):
        if behavior == ERROR_BEHAVIORS.DEFAULT.value:
            self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text + _ERROR_MSG,
                buttons=Buttons.OK,
            )
            self.scopeop.to_intermission("Ending experiment due to error.")

        elif behavior == ERROR_BEHAVIORS.PRECHECK.value:
            self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text + _ERROR_MSG,
                buttons=Buttons.OK,
            )

        elif behavior == ERROR_BEHAVIORS.FLOWCONTROL.value:
            message_result = self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text
                + '\n\nClick "Yes" to continue experiment with flowrate below target, or click "No" to end this run.',
                buttons=Buttons.YN,
            )
            if message_result == QMessageBox.No:
                self.scopeop.to_intermission("Ending experiment due to error.")
            else:
                if self.scopeop.state == "fastflow":
                    self.scopeop.next_state()

    def display_message(
        self,
        icon: QMessageBox.Icon,
        title,
        text,
        buttons=None,
        image=None,
    ):
        self.message_window.close()

        self.message_window = NoCloseMessageBox()
        self.message_window.setWindowIcon(QIcon(ICON_PATH))
        self.message_window.setIcon(icon)
        self.message_window.setWindowTitle(f"{title}")

        self.message_window.setText(f"{text}")

        if buttons is not None:
            self.message_window.setStandardButtons(buttons.value)

        if image is not None:
            layout = self.message_window.layout()

            image_lbl = QLabel()
            image_lbl.setPixmap(QPixmap(image))

            # Row/column span determined using layout.rowCount() and layout.columnCount()
            # TODO: Mypy doesn't like this because of "too many args" and "alignment"
            layout.addWidget(image_lbl, 4, 0, 1, 3, alignment=Qt.AlignCenter)  # type: ignore

        message_result = self.message_window.exec()
        return message_result

    def close_lid_display_message(self):
        while self.scopeop.lid_opened:
            self.display_message(
                QMessageBox.Icon.Information,
                "Lid opened - pausing",
                'The lid is open. Close the lid and press "OK" to resume.',
                buttons=Buttons.OK,
            )

    def _start_setup(self, *args):
        self.lid_handler_enabled = False
        self.display_message(
            QMessageBox.Icon.Warning,
            "DISCLAIMER: RESEARCH USE ONLY",
            f"{RESEARCH_USE_ONLY}",
            buttons=Buttons.OK,
        )
        self.display_message(
            QMessageBox.Icon.Information,
            "Initializing hardware",
            (
                "Remove the CAP module if it is currently on."
                '\n\nClick "OK" once it is removed.'
            ),
            buttons=Buttons.OK,
            image=_IMAGE_REMOVE_PATH,
        )

        self.scopeop_thread.start()
        self.acquisition_thread.start()

        self.form_window.showMaximized()

    def _end_setup(self, *args):
        self.form_window.unfreeze_buttons()

    def _start_form(self, *args):
        self.form_window.showMaximized()

    def save_form(self):
        self.form_metadata = self.form_window.get_form_input()
        self.form_window.reset_parameters()
        self.liveview_window.update_experiment(self.form_metadata)
        self.liveview_window.clear_thumbnails()

        for key in self.form_metadata:
            self.experiment_metadata[key] = self.form_metadata[key]

        # DATA-TODO verify if user input satisfies required format
        # -> if data fails verification, prompt user for correction using "display_message" (defined above)
        # -> if data passes verification, call "self.next_state" to open liveview

        # Assign other metadata parameters
        self.experiment_metadata["scope"] = socket.gethostname()
        self.experiment_metadata["camera"] = CAMERA_SELECTION.name
        self.experiment_metadata[
            "exposure"
        ] = self.scopeop.mscope.camera.exposureTime_ms
        self.experiment_metadata["target_brightness"] = TOP_PERC_TARGET_VAL
        self.experiment_metadata["autofocus_model"] = Path(AUTOFOCUS_MODEL_DIR).stem
        self.experiment_metadata["yogo_model"] = Path(YOGO_MODEL_DIR).stem

        # TODO try a cleaner solution than nested try-excepts?
        # On Git branch
        try:
            self.experiment_metadata["git_branch"] = (
                subprocess.check_output(["git", "symbolic-ref", "--short", "HEAD"])
                .decode("ascii")
                .strip()
            )
            self.experiment_metadata["git_commit"] = (
                subprocess.check_output(["git", "rev-parse", "HEAD"])
                .decode("ascii")
                .strip()
            )
        except subprocess.CalledProcessError:
            # On Git tag (ie. headless)
            try:
                self.experiment_metadata["git_branch"] = (
                    subprocess.check_output(["git", "describe", "--tags"])
                    .decode("ascii")
                    .strip()
                )
                self.experiment_metadata["git_commit"] = (
                    subprocess.check_output(
                        ["git", "rev-list", "--tags", "--max-count=1"]
                    )
                    .decode("ascii")
                    .strip()
                )
            except subprocess.CalledProcessError:
                self.logger.info("No Git branch or tag found.")

        self.scopeop.mscope.data_storage.createNewExperiment(
            self.ext_dir,
            "",
            self.datetime_str,
            self.experiment_metadata,
            PER_IMAGE_METADATA_KEYS,
        )

        sample_type = self.experiment_metadata["sample_type"]
        clinical = sample_type == CLINICAL_SAMPLE
        try:
            self.scopeop.mscope.data_storage.initCountCompensator(clinical)
        except FileNotFoundError as e:
            self.display_message(
                QMessageBox.Icon.Warning,
                "Compensation metrics missing",
                (
                    f"Compensation metrics could not be found for {sample_type[0].lower() + sample_type[1:]}."
                    " Please check that remo-stats-utils repository is up to date."
                    '\n\nClick "OK" to shutoff scope.'
                ),
                buttons=Buttons.OK,
            )
            self.logger.warning(
                f"Compensation metrics could not be found for {sample_type[0].lower() + sample_type[1:]}.\n{e}"
            )
            self.shutoff()
            return

        # Update target flowrate in scopeop
        self.scopeop.target_flowrate = self.form_metadata["target_flowrate"][1]

        self.liveview_window.hide_progress_bar_show_state_label()
        self.to_liveview()

    def _end_form(self, *args):
        if not SIMULATION:
            self.scopeop.lid_opened = self.scopeop.mscope.read_lim_sw()
        else:
            self.scopeop.lid_opened = False

        self.form_window.close()

    def _start_liveview(self, *args):
        self.display_message(
            QMessageBox.Icon.Information,
            "Starting run",
            '1. Insert flow cell\n\n2. Put the CAP module back on\n\n3. Close the lid\n\nClick "OK" once it is closed.',
            buttons=Buttons.OK,
            image=_IMAGE_INSERT_PATH,
        )

        while self.scopeop.lid_opened:
            self.display_message(
                QMessageBox.Icon.Information,
                "Starting run",
                "The lid has not been closed. Please close the lid to proceed.",
                buttons=Buttons.OK,
                image=_IMAGE_INSERT_PATH,
            )

        self.lid_handler_enabled = True
        self.liveview_window.showMaximized()
        self.scopeop.start()

    def _end_liveview(self, *args):
        self.liveview_window.close()

    def _start_intermission(self, msg):
        if msg == "":
            # Retriggered intermission due to race condition
            return

        self.display_message(
            QMessageBox.Icon.Information,
            "Run complete",
            f'{msg} Remove CAP module and flow cell now.\n\nClick "OK" once they are removed.',
            buttons=Buttons.OK,
            image=_IMAGE_REMOVE_PATH,
        )

        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "Run another experiment?",
            'Click "Yes" to start a new run or "No" to shutoff scope.',
            buttons=Buttons.YN,
        )
        if message_result == QMessageBox.No:
            self.shutoff()
        elif message_result == QMessageBox.Yes:
            self.logger.info("Starting new experiment.")
            if not DataStorage.is_there_sufficient_storage(self.ext_dir):
                self.ssd_full_msg_and_exit()
                self.shutoff()
            else:
                try:
                    self.scopeop.rerun()
                except MachineError:
                    self.scopeop.to_intermission(None)
                    self.scopeop.rerun()

    def shutoff(self):
        self.logger.info("Starting oracle shut off.")

        try:
            os.remove(LOCKFILE)
            self.logger.info(f"Removed lockfile ({LOCKFILE}).")
        except FileNotFoundError:
            self.logger.warning(
                f"Lockfile ({LOCKFILE}) does not exist and could not be deleted."
            )

        # Wait for QTimers to shutoff
        self.logger.info("Waiting for acquisition and liveview timer to terminate.")
        while (
            self.acquisition.acquisition_timer.isActive()
            or self.acquisition.liveview_timer.isActive()
        ):
            pass
        self.logger.info("Successfully terminated acquisition and liveview timer.")

        # Shut off hardware
        self.scopeop.mscope.shutoff()

        # Shut off acquisition thread
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()
        self.logger.info("Shut off acquisition thread.")

        # Shut off scopeop thread
        self.scopeop_thread.quit()
        self.scopeop_thread.wait()
        self.logger.info("Shut off scopeop thread.")

        self.form_window.close()
        self.logger.info("Closed experiment form window.")
        self.liveview_window.close()
        self.logger.info("Closed liveview window.")

        self.logger.info("ORACLE SHUT OFF SUCCESSFUL.")
        self.shutoff_done = True

    def emergency_shutoff(self):
        self.logger.warning("Starting emergency oracle shut off.")

        if not self.shutoff_done:

            try:
                os.remove(LOCKFILE)
                self.logger.info(f"Removed lockfile ({LOCKFILE}).")
            except FileNotFoundError:
                self.logger.warning(
                    f"Lockfile ({LOCKFILE}) does not exist and could not be deleted."
                )

            # Shut off hardware
            self.scopeop.mscope.shutoff()

            # Close data storage if it's not already closed
            if self.scopeop.mscope.data_storage.zw.writable:
                self.scopeop.mscope.data_storage.close(
                    self.scopeop.mscope.predictions_handler.get_prediction_tensors()
                )
            else:
                self.logger.info(
                    "Since data storage is already closed, no data storage operations were needed."
                )

            self.logger.info("EMERGENCY ORACLE SHUT OFF SUCCESSFUL.")


if __name__ == "__main__":
    app = ShutoffApplication(sys.argv)
    oracle = Oracle()

    app.connect_signal(oracle.scopeop.shutoff)

    def shutoff_excepthook(type, value, traceback):
        sys.__excepthook__(type, value, traceback)
        try:
            app.shutoff.emit()
            # Pause before shutting off hardware to ensure there are no calls to camera post-shutoff
            sleep(3)
            oracle.emergency_shutoff()
        except Exception as e:
            oracle.logger.fatal(f"EMERGENCY ORACLE SHUT OFF FAILED - {e}")

        sys.exit(1)

    sys.excepthook = shutoff_excepthook

    app.exec()
