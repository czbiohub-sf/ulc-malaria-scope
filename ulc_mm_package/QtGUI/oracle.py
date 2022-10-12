import sys
import numpy as np

from transitions import Machine
from time import perf_counter, sleep

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QThread
from PyQt5.QtGui import QIcon

from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.QtGUI.gui_constants import ICON_PATH

from ulc_mm_package.QtGUI.scope_op import ScopeOp
from ulc_mm_package.QtGUI.acquisition import Acquisition
from ulc_mm_package.QtGUI.form_gui import FormGUI
from ulc_mm_package.QtGUI.liveview_gui import LiveviewGUI

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"
_EXIT_MSG = "Click OK to end experiment."

# Add type to input arguments (mscope, img_signal)

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
            {'name' : 'setup', 
                'on_enter' : [self._start_setup]},
            {'name' : 'form', 
                'on_enter' : [self._start_form], 
                'on_exit' : [self._close_form]},
            {'name' : 'liveview', 
                'on_enter' : [self._start_liveview], 
                'on_exit' : [self._close_liveview, self._open_survey]},
            ]
        Machine.__init__(self, states=states, queued=True, initial='standby')
        self.add_ordered_transitions()
        self.add_transition(trigger='reset', source='*', dest='form', before='_reset')

        # Connect experiment form buttons
        self.form_window.start_btn.clicked.connect(self.save_form)
        self.form_window.exit_btn.clicked.connect(self.shutoff)

        # Connect liveview buttons
        self.liveview_window.exit_btn.clicked.connect(self.shutoff)

        # Connect scopeop signals and slots
        self.scopeop.setup_done.connect(self.to_form)
        self.scopeop.reset_done.connect(self.reset)
        self.scopeop.error.connect(self.error_handler)

        self.scopeop.freeze_liveview.connect(self.acquisition.freeze_liveview)
        self.scopeop.set_period.connect(self.acquisition.set_period)

        self.scopeop.create_timers.connect(self.acquisition.create_timers)
        self.scopeop.start_timers.connect(self.acquisition.start_timers)
        self.scopeop.stop_timers.connect(self.acquisition.stop_timers)

        # Connect acquisition signals and slots
        self.acquisition.update_liveview.connect(self.liveview_window.update_img)

        # Trigger first transition
        self.to_setup()

    def save_form(self):
        # TODO save experiment metadata here

        self.next_state()

    def error_handler(self, title, text):
        self.display_message(
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

        if exit_after:
            msgBox.setText(f"{text} {_EXIT_MSG}")
        else:
            msgBox.setText(f"{text}")

        if cancel:
            msgBox.setStandardButtons(
                QMessageBox.Ok | QMessageBox.Cancel
            )
        else:
            msgBox.setStandardButtons(QMessageBox.Ok)

        if exit_after and msgBox.exec() == QMessageBox.Ok:
            self.shutoff()

        return msgBox.exec()

    def _reset(self, *args):
        reset_query = self.display_message(
            QMessageBox.Icon.Information,
            "Run complete",
            "Start new run?",
            cancel=True,
            )
        if reset_query == QMessageBox.Cancel:
            self.shutoff()
        else:
            print("Running new experiment")
        # TODO add user instructions to remove flow cell before resetting syringe
        # TODO delete current scope data storage

    def _start_setup(self, *args):
        self.scopeop_thread.start()
        self.acquisition_thread.start()

        self.scopeop.setup()
        self.acquisition.get_mscope(self.scopeop.mscope)

    def _start_form(self, *args):
        self.form_window.show()

    def _close_form(self, *args):
        self.form_window.close()

    def _start_liveview(self, *args):
        self.liveview_window.show()
        self.scopeop.start()

    def _close_liveview(self, *args):
        self.liveview_window.close()

    def _open_survey(self, *args):
        pass

    def shutoff(self, *args):

        if self.state == 'liveview':
            # TODO Update data_storage
            # closing_file_future = self.scopeop.mscope.data_storage.close()

            # print("Waiting for the file to finish closing...")
            # while not self.scopeop.mscope.data_storage == None:
            #     sleep(1)
            # print("Successfully closed file.")

            pass

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