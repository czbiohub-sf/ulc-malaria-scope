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
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon, QPixmap

from ulc_mm_package.scope_constants import (
    EXPERIMENT_METADATA_KEYS,
    PER_IMAGE_METADATA_KEYS,
    CAMERA_SELECTION,
    EXT_DIR,
)
from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.processing_constants import (
    TOP_PERC_TARGET_VAL,
    FLOWRATE,
)
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    FLOWCELL_QC_FORM_LINK,
)

from ulc_mm_package.utilities.ngrok_utils import make_tcp_tunnel, NgrokError

from ulc_mm_package.QtGUI.scope_op import ScopeOp
from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.QtGUI.form_gui import FormGUI
from ulc_mm_package.QtGUI.liveview_gui import LiveviewGUI

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"
_ERROR_MSG = ' Click "OK" to end this run.'

_IMAGE_INSERT_PATH = "gui_images/insert_infographic.png"
_IMAGE_REMOVE_PATH = "gui_images/remove_infographic.png"


class Buttons(enum.Enum):
    OK = QMessageBox.Ok
    CANCEL = QMessageBox.Cancel | QMessageBox.Ok
    YN = QMessageBox.No | QMessageBox.Yes


class Oracle(Machine):
    def __init__(self):

        # Save startup datetime
        self.datetime_str = datetime.now().strftime(DATETIME_FORMAT)

        # Setup directory for logs
        log_dir = path.join(EXT_DIR, "logs")
        if not path.isdir(log_dir):
            mkdir(log_dir)

        # Setup logger
        fileConfig(
            fname="../logger.config",
            defaults={"filename": path.join(log_dir, f"{self.datetime_str}.log")},
        )
        self.logger = logging.root
        self.logger.info("STARTING ORACLE.")

        # Instantiate GUI windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()
        self.message_window = QMessageBox()

        # Instantiate variables
        self._init_variables()

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp(self.acquisition.update_scopeop)
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        self.scopeop_thread.started.connect(self.scopeop.setup)

        # Configure state machine
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
            before=self._init_variables,
        )

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.shutoff)

        # Connect liveview buttons
        self.liveview_window.pause_btn.clicked.connect(self.pause_handler)
        self.liveview_window.exit_btn.clicked.connect(self.exit_handler)

        # Connect scopeop signals and slots
        self.scopeop.setup_done.connect(self.next_state)
        self.scopeop.experiment_done.connect(self.next_state)
        self.scopeop.reset_done.connect(self.rerun)

        self.scopeop.yield_mscope.connect(self.acquisition.get_mscope)

        self.scopeop.error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.enable_pause.connect(self.liveview_window.enable_pause)
        self.scopeop.send_pause.connect(self.pause_receiver)

        self.scopeop.create_timers.connect(self.acquisition.create_timers)
        self.scopeop.start_timers.connect(self.acquisition.start_timers)
        self.scopeop.stop_timers.connect(self.acquisition.stop_timers)

        self.scopeop.update_state.connect(self.liveview_window.update_state)
        self.scopeop.update_img_count.connect(self.liveview_window.update_img_count)
        self.scopeop.update_cell_count.connect(self.liveview_window.update_cell_count)
        self.scopeop.update_msg.connect(self.liveview_window.update_msg)

        self.scopeop.update_flowrate.connect(self.liveview_window.update_flowrate)
        self.scopeop.update_focus.connect(self.liveview_window.update_focus)

        # Connect acquisition signals and slots
        self.acquisition.update_liveview.connect(self.liveview_window.update_img)

        # Get tcp tunnel
        try:
            tcp_addr = make_tcp_tunnel()
            self.logger.info(f"SSH address is {tcp_addr}.")
            self.liveview_window.update_tcp(tcp_addr)
        except NgrokError:
            self.display_message(
                QMessageBox.Icon.Warning,
                "SSH tunnel failed",
                (
                    "Could not create SSH tunnel so the scope cannot be accessed remotely unless it is rebooted."
                    '\n\nClick "OK" to continue running without SSH.'
                ),
                buttons=Buttons.OK,
            )

            self.logger.warning("SSH address could not be found.")
            self.liveview_window.update_tcp("unavailable")

        # Trigger first transition
        self.next_state()

    def pause_receiver(self, title, message):
        self.pause_handler(
            icon=QMessageBox.Icon.Warning,
            title=title,
            message=message,
            buttons=Buttons.OK,
        )
        
    def pause_handler(self, 
                        icon=QMessageBox.Icon.Information, 
                        title="Pause run?", 
                        message=(
                                "While paused, you can add more sample to the flow cell, "
                                "without losing the current brightness and focus calibration."
                                '\n\nClick "OK" to pause this run and wait for the next dialog before removing the condensor.'
                                ),
                        buttons=Buttons.CANCEL):
        message_result = self.display_message(
            icon,
            title,
            message,
            buttons=buttons,
        )
        if message_result == QMessageBox.Ok:
            self.scopeop.to_pause()
        else:
            return

        sleep(2)
        self.display_message(
            QMessageBox.Icon.Information,
            "Paused run",
            (
                "The condensor can now be removed."
                '\n\nAfter adding the sample and replacing the condensor, click "OK" to resume this run.'
            ),
            buttons=Buttons.OK,
        )
        self.scopeop.unpause()

    def exit_handler(self):
        message_result = self.display_message(
            QMessageBox.Icon.Information,
            "End run?",
            'Click "OK" to end this run.',
            buttons=Buttons.CANCEL,
        )
        if message_result == QMessageBox.Ok:
            self.scopeop.to_intermission()

    def error_handler(self, title, text, abort):
        self.display_message(
            QMessageBox.Icon.Critical,
            title,
            text + _ERROR_MSG,
            buttons=Buttons.OK,
            abort=abort,
        )

        if not abort:
            self.scopeop.to_intermission()

    def display_message(
        self, icon: QMessageBox.Icon, title, text, buttons=None, image=None, abort=False
    ):
        self.message_window.close()

        self.message_window = QMessageBox()
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

        if abort:
            self.shutoff()

        return message_result

    def _init_variables(self):
        # Instantiate metadata dicts
        self.form_metadata = None
        self.experiment_metadata = {key: None for key in EXPERIMENT_METADATA_KEYS}

        self.liveview_window.set_infopanel_vals()

    def _start_setup(self):
        self.display_message(
            QMessageBox.Icon.Information,
            "Initializing hardware",
            (
                "If there is a flow cell in the scope, remove it now."
                '\n\nClick "OK" once the flow cell is removed.'
            ),
            buttons=Buttons.OK,
            image=_IMAGE_REMOVE_PATH,
        )

        self.scopeop_thread.start()
        self.acquisition_thread.start()

        self.form_window.show()

    def _end_setup(self):
        self.form_window.unfreeze_buttons()

    def _start_form(self):
        self.form_window.show()

    def save_form(self):
        self.form_metadata = self.form_window.get_form_input()
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
            "", self.datetime_str, self.experiment_metadata, PER_IMAGE_METADATA_KEYS
        )

        # Update target flowrate in scopeop
        self.scopeop.target_flowrate = self.form_metadata["target_flowrate"][1]

        self.next_state()

    def _end_form(self):
        self.form_window.close()

    def _start_liveview(self):
        self.display_message(
            QMessageBox.Icon.Information,
            "Starting run",
            'Insert flow cell now.\n\nClick "OK" once it is in place.',
            buttons=Buttons.OK,
            image=_IMAGE_INSERT_PATH,
        )

        self.liveview_window.show()
        self.scopeop.start()

    def _end_liveview(self):
        self.liveview_window.close()

        self.logger.debug("Opening survey.")
        webbrowser.open(FLOWCELL_QC_FORM_LINK, new=0, autoraise=True)

    def _start_intermission(self):
        self.display_message(
            QMessageBox.Icon.Information,
            "Run complete",
            'Remove flow cell now.\n\nClick "OK" once it is removed.',
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
            self.scopeop.rerun()

    def shutoff(self):
        # Wait for QTimers to shutoff
        self.logger.debug("Waiting for acquisition and liveview timer to terminate.")
        while (
            self.acquisition.acquisition_timer.isActive()
            or self.acquisition.liveview_timer.isActive()
        ):
            pass
        self.logger.debug("Successfully terminated acquisition and liveview timer.")

        # Shut off hardware
        self.scopeop.mscope.shutoff()

        # Shut off acquisition thread
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()
        self.logger.debug("Shut off acquisition thread.")

        # Shut off scopeop thread
        self.scopeop_thread.quit()
        self.scopeop_thread.wait()
        self.logger.debug("Shut off scopeop thread.")

        self.form_window.close()
        self.logger.debug("Closed experiment form window.")
        self.liveview_window.close()
        self.logger.debug("Closed liveview window.")

        self.logger.info("SHUTTING OFF ORACLE.")

        self.message_window.close()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec())
