import sys
import numpy as np

from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSlot
from PyQt5.QtGui import QIcon

from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    CAMERA_SELECTION,
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
)

from ulc_mm_package.QtGUI.scope_op import ScopeOp
from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.QtGUI.form_gui import FormGUI
from ulc_mm_package.QtGUI.liveview_gui import LiveviewGUI

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

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
        self.acquisition_thread = QThread()
        self.acquisition.moveToThread(self.acquisition_thread)

        # Instantiate scope operator and thread
        self.scopeop = ScopeOp(self.acquisition.update_scopeop)
        self.scopeop_thread = QThread()
        self.scopeop.moveToThread(self.scopeop_thread)

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
                'on_exit' : [self._close_liveview, self._open_survey]},
            ]

        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='reset', source='*', dest='standby', after='_reset')

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.end)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.end)

        # Connect scopeop signals and slots
        self.scopeop.precheck_done.connect(self.next_state)
        self.scopeop.error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.create_timers.connect(self.acquisition.create_timers)
        self.scopeop.start_timers.connect(self.acquisition.start_timers)
        self.scopeop.stop_timers.connect(self.acquisition.stop_timers)

        # Trigger first transition
        self.to_precheck()

    def save_form(self):
        self.next_state()

    def error_handler(self, title, text):
        _ = self._display_message(
            QMessageBox.Icon.Critical,
            title,
            text,
            exit_after=True,
            )

    def display_message(self, icon, title, text, cancel=False, exit_after=False):
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
        self.acquisition.acquisition_timer.stop()
        self.acquisition.count = 0
        # delete current scope?

    def _start_precheck(self, *args):
        self.scopeop_thread.start()

        self.scopeop.precheck()
        self.acquisition.get_mscope(self.scopeop.mscope)
        # self.acquisition.get_img()
        # self.acquisition.get_signal(self.scopeop.request_img)

    def _start_form(self, *args):
        self.form_window.show()

    def _close_form(self, *args):
        self.form_window.close()

    def _start_liveview(self, *args):
        self.liveview_window.show()

        self.acquisition.update_liveview.connect(self.liveview_window.update_img)
        self.acquisition_thread.start()
        # self.acquisition.get_img()
        # self.acquisition.start()
        
        # self.acquisition.acquisition_timer.start(ACQUISITION_PERIOD)
        # self.acquisition.liveview_timer.start(ACQUISITION_PERIOD)

        self.scopeop.start()


    def _close_liveview(self, *args):
        self.scopeop.to_standby()
        self.acquisition.update_liveview.disconnect(self.liveview_window.update_img)

        self.liveview_window.close()

    def _open_survey(self, *args):
        pass

    def end(self, *args):
        # closing_file_future = self.scopeop.mscope.data_storage.close()

        print("Waiting for the file to finish closing...")
        # while not closing_file_future.done():
        #     sleep(1)
        print("Successfully closed file.")

        self.scopeop.shutoff()
        print("Waiting for timer to terminate...")
        while self.acquisition.acquisition_timer.isActive() or self.acquisition.liveview_timer.isActive():
            pass
        print("Successfully terminated timer.")
        
        self.acquisition_thread.quit()
        self.acquisition_thread.wait()
        
        self.scopeop_thread.quit()
        self.scopeop_thread.wait()
        
        print("Exiting program")
        quit()   
       

if __name__ == "__main__":

    app = QApplication(sys.argv)
    oracle = Oracle()
    sys.exit(app.exec_())