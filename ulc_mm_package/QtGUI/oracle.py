import sys
import numpy as np

from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtWidgets import QtWidgets, QtCore, QMessageBox
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon

from ulc_mm_package.image_processing.processing_constants import (
    TIMEOUT_PERIOD,
    ICON_PATH,
    CAMERA_SELECTION,
    EXPERIMENT_METADATA_KEYS, 
)

from ulc_mm_package.QtGUI.scope_op import ScopeOp
from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.QtGUI.form_gui import FormGUI
from ulc_mm_package.QtGUI.liveview_gui import LiveviewGUI

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

# Add type to input arguments (mscope, img_signal)
# Does PyQt5.QtWidgets need to be imported?
# Check 4036 notes

# TODOs
# TH sensor needs to be simulated too

# NICE TO HAVE
# Use "on_exception" to trigger exception handler
# Validate experiment form inputs
# Implement exception handling for camera


class Oracle(Machine):

    def __init__(self, *args, **kwargs):
        # Instantiate windows
        self.form_window = FormGUI()
        self.liveview_window = LiveviewGUI()

        # Instantiate camera acquisition and thread
        self.acquisition = Acquisition()
        self.acquisition_thread = QtCore.QThread()
        self.acquisition.moveToThread(self.acquisition_thread)
        # self.acquisition_thread.started.connect(self.acquisition.run)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp(self.acquisition.update_scopeop)
        self.scopeop_thread = QtCore.QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

        # Connect scope operator signal and slot
        self.scopeop.error.connect(self.error_handler)

        # Configure state machine
        states = [
            {'name' : 'standby'},
            {'name' : 'precheck', 
                'on_enter' : [self._start_precheck]},
            {'name' : 'form', 
                'on_enter' : [self._start_form], 
                'on_exit' : [self._close_form]},
            {'name' : 'liveview', 
                'on_enter' : [self._start_liveview], 
                'on_exit' : [self._close_liveview]},
            # {'name' : 'survey', 'on_enter' : ['open_survey']},
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='reset', source='*', dest='standby', after='_reset')

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self._save_form)
        self.form_window.exit_btn.clicked.connect(self.end)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.end)

        # Connect scopeop signals and slots
        self.scopeop.precheck_done.connect(self.next_state)
        self.scopeop.freeze_liveview.connect(self._freeze_liveview)

        # Start scopeop thread
        self.scopeop_thread.start()

        # Trigger first transition
        self.to_precheck()

    def _freeze_liveview(self, freeze):
        if freeze:
            self.acquisition.update_liveview.disconnect(self.liveview_window.update_img)
        else:            
            self.acquisition.update_liveview.connect(self.liveview_window.update_img)

    def _display_message(self, icon, title, text, cancel=False, exit_after=False):
        msgBox = QMessageBox()
        msgBox.setWindowIcon(QIcon(ICON_PATH))
        msgBox.setIcon(icon)
        msgBox.setWindowTitle(f"{title}")
        msgBox.setText(f"{text}")

        if cancel:
            msgBox.setStandardButtons(
                QMessageBox.Ok | QMessageBox.Cancel
            )
        else:
            msgBox.setStandardButtons(QMessageBox.Ok)

        if exit_after and msgBox.exec() == QMessageBox.Ok:
            self.end()

        return msgBox.exec()

    def _reset(self, *args):
        self.timer.stop()
        self.acquisition.count = 0
        # delete current scope?

    def _start_precheck(self, *args):
        self.scopeop.precheck()
        self.acquisition.get_mscope(self.scopeop.mscope)

    def _start_form(self, *args):
        self.form_window.show()

    def _save_form(self, *args):
        try:
            # TBD implement actual save here
            # self.scopeop.mscope.data_storage.createNewExperiment(self.form_window.get_form_input())
            pass
        # TODO target correct exception here
        except Exception as e:
            print(e)
            _ = self._display_message(
                QMessageBox.Icon.Warning,
                "Invalid form input",
                "The following entries are invalid:",   # Add proper warnings here
                exit_after=True,
                )

        self.next_state()

    def _close_form(self, *args):
        self.form_window.close()

    def _start_liveview(self, *args):
        self.liveview_window.show()

        self.acquisition.update_liveview.connect(self.liveview_window.update_img)
        self.acquisition_thread.start()

        self.scopeop.start()
        
        self.acquisition.timer.start(TIMEOUT_PERIOD)

    def _close_liveview(self, *args):
        self.scopeop.to_standby()
        self.acquisition.update_liveview.disconnect(self.liveview_window.update_img)

        self.liveview_window.close()

    def error_handler(self, title, text):
        _ = self._display_message(
            QMessageBox.Icon.Error,
            title,
            text,
            exit_after=True,
            )

    def end(self, *args):
        # closing_file_future = self.scopeop.mscope.data_storage.close()
        self.scopeop.mscope.pneumatic_module.setDutyCycle(self.scopeop.mscope.pneumatic_module.getMaxDutyCycle())

        print("Waiting for the file to finish closing...")
        # while not closing_file_future.done():
        #     sleep(1)
        print("Successfully closed file.")

        # self.acquisition.running = False
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()
        print("Exiting program")
        quit()   
       

if __name__ == "__main__":

    app = QtWidgets.QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec_())