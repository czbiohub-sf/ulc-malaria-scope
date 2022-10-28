""" High-level state machine manager.

The Oracle sees all and knows all. 
It owns all GUI windows, threads, and worker objects (ScopeOp and Acquisition).

"""

import sys
import webbrowser
import numpy as np

from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtWidgets import QApplication, QMessageBox, QLabel
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon, QPixmap

from ulc_mm_package.image_processing.processing_constants import (
    EXPERIMENT_METADATA_KEYS,
)
from ulc_mm_package.QtGUI.gui_constants import ICON_PATH, FLOWCELL_QC_FORM_LINK

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


class Oracle(Machine):
    def __init__(self):

        # Instantiate GUI windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()
        self.dialog_window = QMessageBox()

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp()
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Configure state machine
        states = [
            {
                "name": "standby",
            },
            {
                "name": "setup",
                "on_enter": [self._start_setup],
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
        self.add_transition(trigger="rerun", source="intermission", dest="form")

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.shutoff)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.exit_handler)

        # Connect scopeop signals and slots
        self.scopeop.setup_done.connect(self.next_state)
        self.scopeop.experiment_done.connect(self.next_state)
        self.scopeop.reset_done.connect(self.rerun)

        self.scopeop.error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.create_timers.connect(self.acquisition.create_timers)
        self.scopeop.start_timers.connect(self.acquisition.start_timers)
        self.scopeop.stop_timers.connect(self.acquisition.stop_timers)

        self.scopeop.update_infopanel.connect(self.liveview_window.update_infopanel)

        # Connect acquisition signals and slots
        self.acquisition.update_liveview.connect(self.liveview_window.update_img)

        # Trigger first transition
        self.next_state()

    def exit_handler(self):
        dialog_result = self.display_message(
            QMessageBox.Icon.Information,
            "End run?",
            'Click "OK" to end this run.',
            cancel=True,
        )
        if dialog_result == QMessageBox.Ok:
            self.scopeop.to_intermission()

    def error_handler(self, title, text):
        self.display_message(
            QMessageBox.Icon.Critical,
            title,
            text + _ERROR_MSG,
        )

        self.scopeop.to_intermission()

    def display_message(
        self, icon: QMessageBox.Icon, title, text, cancel=False, image=None
    ):

        self.dialog_window.close()

        self.dialog_window = QMessageBox()
        self.dialog_window.setWindowIcon(QIcon(ICON_PATH))
        self.dialog_window.setIcon(icon)
        self.dialog_window.setWindowTitle(f"{title}")

        self.dialog_window.setText(f"{text}")

        if cancel:
            self.dialog_window.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        else:
            self.dialog_window.setStandardButtons(QMessageBox.Ok)
        self.dialog_window.setDefaultButton(QMessageBox.Ok)

        if not image == None:
            layout = self.dialog_window.layout()

            image_lbl = QLabel()
            image_lbl.setPixmap(QPixmap(image))

            # Row/column span determined using layout.rowCount() and layout.columnCount()
            layout.addWidget(image_lbl, 4, 0, 1, 3, alignment=Qt.AlignCenter)

        dialog_result = self.dialog_window.exec()

        return dialog_result

    def _start_setup(self):
        self.display_message(
            QMessageBox.Icon.Information,
            "Initializing hardware",
            'If there is a flow cell in the scope, remove it now. Click "OK" once it is removed.',
            image=_IMAGE_REMOVE_PATH,
        )

        self.scopeop_thread.start()
        self.acquisition_thread.start()

        self.scopeop.setup()
        self.acquisition.get_mscope(self.scopeop.mscope)
        self.scopeop.get_signals(
            self.acquisition.update_scopeop, 
            self.acquisition.acquisition_timer
        )

    def _start_form(self):
        # Instantiate metadata dicts
        self.form_metadata = None
        self.experiment_metadata = {key : None for key in EXPERIMENT_METADATA_KEYS}

        self.form_window.show()

    def save_form(self):
        self.form_metadata = self.form_window.get_form_input()
        self.liveview_window.update_experiment(self.form_metadata)

        for key in self.form_metadata:
            self.experiment_metadata[key] = self.form_metadata[key]

        # TODO Fill in other experiment metadata here, and initialize data_storage object
        # Only move on to next state if data is verified

        self.next_state()

    def _end_form(self):
        self.form_window.close()

    def _start_liveview(self):
        self.display_message(
            QMessageBox.Icon.Information,
            "Starting run",
            'Insert flow cell now. Click "OK" once it is in place.',
            image=_IMAGE_INSERT_PATH,
        )

        self.liveview_window.show()
        self.scopeop.start()

    def _end_liveview(self):
        self.liveview_window.close()

        print("ORACLE: Opening survey")
        webbrowser.open(FLOWCELL_QC_FORM_LINK, new=0, autoraise=True)

    def _start_intermission(self):
        dialog_result = self.display_message(
            QMessageBox.Icon.Information,
            "Run complete",
            'Remove flow cell now. Once it is removed, click "OK" to start a new run or "Cancel" to shutoff.',
            cancel=True,
            image=_IMAGE_REMOVE_PATH,
        )
        if dialog_result == QMessageBox.Cancel:
            self.shutoff()
        elif dialog_result == QMessageBox.Ok:
            print("ORACLE: Running new experiment")
            self.scopeop.rerun()

    def shutoff(self):
        # End experiment
        self.scopeop.end()

        # Wait for QTimers to shutoff
        print("ORACLE: Waiting for timer to terminate...")
        while (
            self.acquisition.acquisition_timer.isActive()
            or self.acquisition.liveview_timer.isActive()
        ):
            pass
        print("ORACLE: Successfully terminated timer.")

        # Shut off hardware
        self.scopeop.mscope.shutoff()
        # TODO does this shutoff before scopeop quits?

        # Shut off acquisition thread
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()

        # Shut off scopeop thread
        self.scopeop_thread.quit()
        self.scopeop_thread.wait()

        print("ORACLE: Exiting program")
        self.form_window.close()
        self.liveview_window.close()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec_())
