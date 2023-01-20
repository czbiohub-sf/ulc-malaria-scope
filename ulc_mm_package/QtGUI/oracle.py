""" High-level state machine manager.

The Oracle sees all and knows all.
It owns all GUI windows, threads, and worker objects (ScopeOp and Acquisition).

"""

import sys
import socket
import webbrowser
import enum
import logging
import numpy as np

from os import listdir
from transitions import Machine
from time import perf_counter, sleep
from logging.config import fileConfig
from os import path, mkdir
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QLabel,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap

from ulc_mm_package.scope_constants import (
    EXPERIMENT_METADATA_KEYS,
    PER_IMAGE_METADATA_KEYS,
    CAMERA_SELECTION,
    SSD_DIR,
    VERBOSE,
    SIMULATION,
    SSD_NAME,
)
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.data_storage import DataStorage
from ulc_mm_package.image_processing.processing_constants import (
    TOP_PERC_TARGET_VAL,
    FLOWRATE,
)
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    FLOWCELL_QC_FORM_LINK,
    ERROR_BEHAVIORS,
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


class BUTTONS(enum.Enum):
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

        # Disable [x] button
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)


class Oracle(Machine):
    def __init__(self):
        self.shutoff_done = False

        # Save startup datetime
        self.datetime_str = datetime.now().strftime(DATETIME_FORMAT)

        # Instantiate message dialog
        self.message_window = QMessageBox()

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

        # Instantiate and configure Oracle elements
        self._set_variables()
        self._init_threads()
        self._init_states()
        self._init_sigslots()

        # Get tcp tunnel
        self._init_tcp()

        # Trigger first transition
        self.next_state()

    def _set_variables(self):
        # Instantiate metadata dicts
        self.form_metadata = None
        self.experiment_metadata = {key: None for key in EXPERIMENT_METADATA_KEYS}

        self.liveview_window.set_infopanel_vals()

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
        self.liveview_window.pause_btn.clicked.connect(self.pause_handler)
        self.liveview_window.exit_btn.clicked.connect(self.liveview_exit_handler)
        self.liveview_window.close_event.connect(self.close_handler)

        # Connect scopeop signals and slots
        self.scopeop.setup_done.connect(self.next_state)
        self.scopeop.experiment_done.connect(self.next_state)
        self.scopeop.reset_done.connect(self.rerun)

        self.scopeop.yield_mscope.connect(self.acquisition.get_mscope)

        self.scopeop.precheck_error.connect(self.shutoff)
        self.scopeop.default_error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.send_pause.connect(self.pause_receiver)

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

        # Connect acquisition signals and slots
        self.acquisition.update_liveview.connect(self.liveview_window.update_img)
        self.acquisition.update_infopanel.connect(self.scopeop.update_infopanel)

    def _init_tcp(self):
        try:
            tcp_addr = make_tcp_tunnel()
            self.logger.info(f"SSH address is {tcp_addr}.")
            self.liveview_window.update_tcp(tcp_addr)
            send_ngrok_email()
        except NgrokError as e:
            self.display_message(
                QMessageBox.Icon.Warning,
                "SSH tunnel failed",
                (
                    "Could not create SSH tunnel, so the scope cannot be accessed remotely. "
                    "The SSH tunnel is only recreated when the scope is rebooted."
                    '\n\nClick "OK" to continue running without SSH.'
                ),
                buttons=BUTTONS.OK,
            )
            self.logger.warning(f"SSH address could not be found - {e}")
            self.liveview_window.update_tcp("unavailable")
        except EmailError as e:
            self.display_message(
                QMessageBox.Icon.Warning,
                "SSH email failed",
                self.logger.info("STARTING ORACLE.")(
                    "Could not automatically email SSH tunnel address. "
                    "If SSH is needed, please use the address printed in the liveviewer or terminal. "
                    '\n\nClick "OK" to continue running.'
                ),
                buttons=BUTTONS.OK,
            )
            self.logger.warning(f"SSH address could not be emailed - {e}")

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
            except (FileNotFoundError, IndexError) as e:
                print(
                    f"Could not find any folders within {SSD_DIR}. Check that the SSD is plugged in."
                )
                self.display_message(
                    QMessageBox.Icon.Critical,
                    "SSD not found",
                    f"Could not find any folders within {SSD_DIR}. Check that the SSD is plugged in."
                    + _ERROR_MSG,
                    buttons=BUTTONS.OK,
                )
                sys.exit(1)
        print(f"Saving data to {self.ext_dir}")

        if not DataStorage.is_there_sufficient_storage(self.ext_dir):
            self.ssd_full_msg_and_exit()
            sys.exit(1)

    def ssd_full_msg_and_exit(self):
        self.logger.warning(
            f"The SSD is full. Please eject and then replace the SSD with a new one. Thank you!"
        )
        self.display_message(
            QMessageBox.Icon.Critical,
            "SSD is full",
            f"The SSD is full. Data cannot be saved if the SSD is full. Please eject and then replace the SSD with a new one. Thank you!"
            + _ERROR_MSG,
            buttons=BUTTONS.OK,
        )

    def pause_receiver(self, title, message):
        self.scopeop.to_pause()

        self.pause_handler(
            icon=QMessageBox.Icon.Warning,
            title=title,
            message=message,
            buttons=BUTTONS.OK,
            pause_done=True,
        )

    def pause_handler(
        self,
        icon=QMessageBox.Icon.Information,
        title="Pause run?",
        message=(
            "While paused, you can add more sample to the flow cell, "
            "without losing the current brightness and focus calibration. "
            "After pausing, the scope will restart the calibration steps."
            '\n\nClick "OK" to pause this run and wait for the next dialog before removing the CAP module.'
        ),
        buttons=BUTTONS.CANCEL,
        pause_done=False,
    ):
        message_result = self.display_message(
            icon,
            title,
            message,
            buttons=buttons,
        )
        if message_result == QMessageBox.Cancel:
            return
        elif not pause_done:
            self.scopeop.to_pause()

        sleep(2)
        self.display_message(
            QMessageBox.Icon.Information,
            "Paused run",
            (
                "The CAP module can now be removed."
                "\n\nPlease empty both reservoirs and reload 12 uL of fresh "
                "diluted blood (from the same participant) into the sample reservoir. Make sure to close the lid after."
                '\n\nAfter reloading the reservoir and closing the lid, click "OK" to resume this run.'
            ),
            buttons=BUTTONS.OK,
            image=_IMAGE_RELOAD_PATH,
        )
        self.scopeop.unpause()

    def close_handler(self):
        self.display_message(
            QMessageBox.Icon.Warning,
            "Improper exit",
            (
                'Please close this window using the "Exit" button instead. '
                'This ensures proper shutoff of the scope hardware. '
            ),
            buttons=BUTTONS.OK,
        )
    def form_exit_handler(self):
        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "End experiment?",
            'Click "OK" to end the experiment and shutoff the scope.',
            buttons=BUTTONS.CANCEL,
        )
        if message_result == QMessageBox.Ok:
            self.shutoff()

    def liveview_exit_handler(self):
        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "End run?",
            'Click "OK" to end this run.',
            buttons=BUTTONS.CANCEL,
        )
        if message_result == QMessageBox.Ok:
            self.scopeop.to_intermission("Ending experiment due to user prompt.")

    def error_handler(self, title, text, behavior):
        if behavior == ERROR_BEHAVIORS.DEFAULT.value:
            self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text + _ERROR_MSG,
                buttons=BUTTONS.OK,
            )
            self.scopeop.to_intermission("Ending experiment due to error.")

        elif behavior == ERROR_BEHAVIORS.INSTANT_ABORT.value:
            self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text + _ERROR_MSG,
                buttons=BUTTONS.OK,
            )

        elif behavior == ERROR_BEHAVIORS.YN.value:
            message_result = self.display_message(
                QMessageBox.Icon.Critical,
                title,
                text
                + '\n\nClick "Yes" to continue experiment with flowrate below target, or click "No" to end this run.',
                buttons=BUTTONS.YN,
            )
            if message_result == QMessageBox.No:
                self.scopeop.to_intermission("Ending experiment due to error.")
            else:
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

        if buttons != None:
            self.message_window.setStandardButtons(buttons.value)

        if image != None:
            layout = self.message_window.layout()

            image_lbl = QLabel()
            image_lbl.setPixmap(QPixmap(image))

            # Row/column span determined using layout.rowCount() and layout.columnCount()
            layout.addWidget(image_lbl, 4, 0, 1, 3, alignment=Qt.AlignCenter)

        message_result = self.message_window.exec()
        return message_result

    def _start_setup(self, *args):
        self.display_message(
            QMessageBox.Icon.Information,
            "Initializing hardware",
            (
                "Remove the CAP module if it is currently on."
                '\n\nClick "OK" once it is removed.'
            ),
            buttons=BUTTONS.OK,
            image=_IMAGE_REMOVE_PATH,
        )

        self.scopeop_thread.start()
        self.acquisition_thread.start()

        self.form_window.show()

    def _end_setup(self, *args):
        self.form_window.unfreeze_buttons()

    def _start_form(self, *args):
        self.form_window.show()

    def save_form(self):
        self.form_metadata = self.form_window.get_form_input()
        self.form_window.reset_parameters()
        self.liveview_window.update_experiment(self.form_metadata)

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

        self.scopeop.mscope.data_storage.createNewExperiment(
            self.ext_dir,
            "",
            self.datetime_str,
            self.experiment_metadata,
            PER_IMAGE_METADATA_KEYS,
        )

        # Update target flowrate in scopeop
        self.scopeop.target_flowrate = self.form_metadata["target_flowrate"][1]

        self.next_state()

    def _end_form(self, *args):
        self.form_window.close()

    def _start_liveview(self, *args):
        self.display_message(
            QMessageBox.Icon.Information,
            "Starting run",
            'Insert flow cell and replace CAP module now. Make sure to close the lid after.\n\nClick "OK" once it is closed.',
            buttons=BUTTONS.OK,
            image=_IMAGE_INSERT_PATH,
        )

        self.liveview_window.show()
        self.scopeop.start()

    def _end_liveview(self, *args):
        self.liveview_window.close()

        self.logger.info("Opening survey.")
        webbrowser.open(FLOWCELL_QC_FORM_LINK, new=0, autoraise=True)

    def _start_intermission(self, msg):
        self.display_message(
            QMessageBox.Icon.Information,
            "Run complete",
            f'{msg} Remove CAP module and flow cell now.\n\nClick "OK" once they are removed.',
            buttons=BUTTONS.OK,
            image=_IMAGE_REMOVE_PATH,
        )

        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "Run another experiment?",
            'Click "Yes" to start a new run or "No" to shutoff scope.',
            buttons=BUTTONS.YN,
        )
        if message_result == QMessageBox.No:
            self.shutoff()
        elif message_result == QMessageBox.Yes:
            self.logger.info("Starting new experiment.")
            if not DataStorage.is_there_sufficient_storage(self.ext_dir):
                self.ssd_full_msg_and_exit()
                self.shutoff()
            else:
                self.scopeop.rerun()

    def shutoff(self):
        self.logger.info("Starting oracle shut off.")

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
            # Close data storage if it's not already closed
            if self.scopeop.mscope.data_storage.zw.writable:
                self.scopeop.mscope.data_storage.close()
            else:
                self.logger.info(
                    "Since data storage is already closed, no data storage operations were needed."
                )

            # Shut off hardware
            self.scopeop.mscope.shutoff()

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
