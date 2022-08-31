import sys
import csv
import traceback
import numpy as np

from transitions import Machine

from typing import Dict
from time import perf_counter, sleep
from os import listdir, mkdir, path
from datetime import datetime, timedelta
from PyQt5 import uic        # TODO DELETE THIS
# TODO organize these imports
from PyQt5.QtWidgets import (
    QDialog, QMessageBox,
    QMainWindow, QApplication, QGridLayout,
    QTabWidget, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap, QIcon
from cv2 import imwrite
from qimage2ndarray import array2qimage

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# ================ Misc constants ================ #
_ICON_PATH = "CZB-logo.png"
_FORM_PATH = "user_form.ui"
VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"

#CLEAN UP NOTE??

class Controller(Machine):

    def __init__(self, *args, **kwargs):

        # super(LiveviewGUI, self).__init__(*args, **kwargs)

        # # Load the ui
        # self._loadUI()
        # self.exit_btn.clicked.connect(self.exit)

        states = ['standby', 'form entry', 'setup', 'running']
        Machine.__init__(self, states=states, initial='standby')

        # Initialize the state machine
        # self.machine = Machine(model=self, states=states, initial='standby')

        # use conditions for re-running with experiment form
        # Add transitions
        self.add_transition(trigger='open_form', source='standby', dest='form entry', before="load_form")
        self.add_transition(trigger='open_liveview', source='form entry', dest='setup', before="load_liveview")
        self.add_transition(trigger='run', source='setup', dest='running')
        self.add_transition(trigger='exit', source='*', dest='standby')
        
        self.form_window = FormGUI()
        self.form_window.btnStartExperiment.clicked.connect(self.open_liveview)
        
        try:
            self.main()
        except Exception as e:
            print(e)
            quit()
            
    def main(self):
        
        print(self.state)
        
        self.open_form()
        print(self.state)
        # self.form_window = FormGUI()
        # self.form_window.hide()
        # # self.open_form()
        # quit()
        # print(self.state)
        # # self.open_form()
        
        # print("Done?")
        # quit()

        # while True:
        #     if self.state == 'setup':
        #         print("setting up")
                
        #     if self.state == 'run':
        #         print("running")

    # def form_to_liveview(self):
    #     # TODO switch this to close() if getAllParameters() doesn't need to be called
    #     self.form_window.hide()
    #     print("TADA")
    #     # self.s
    #     # TODO switch this to a before transition method
    #     self.open_liveview()
        
        
    def load_form(self):
        print(self.state)
        print("I'm here")
        self.form_window.show()
        
        # sleep(100)

        # Set up event handler
        # self.form_window.btnStartExperiment.clicked.connect(self.open_liveview)

    # def btnStartExperimentHandler(self):

    #     # self.form_window.experiment_name = self.form_window.txtExperimentName.text()
    #     # self.form_window.flowcell_id = self.form_window.txtFlowCellID.text()

    #     # TODO switch this to close() if getAllParameters() doesn't need to be called
    #     self.form_window.hide()
    #     # TODO switch this to a before transition method
    #     self.open_liveview()
        
    def load_liveview(self, *args):
        # NOTE WHAT IS THIS ARG???
        print(*args)
        self.form_window.hide()
        print("TADA")
        # self.s
    #     # TODO switch this to a before transition method
        # self.open_liveview()
        print("TEMP setup tbd here")
        quit()

    def exit(self):
        quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()
        
class FormGUI(QDialog):
    """Form to input experiment parameters"""
    def __init__(self, *args, **kwargs):
        
        print('init')
        super(FormGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_FORM_PATH, self)
        self.setWindowIcon(QIcon(_ICON_PATH))

        # Set the focus order
        self.setTabOrder(self.txtExperimentName, self.txtFlowCellID)
        self.setTabOrder(self.txtFlowCellID, self.btnStartExperiment)
        self.txtExperimentName.setFocus()

        # Parameters
        self.flowcell_id = ""
        self.experiment_name = ""

        # Set up event handlers
        # TODO change button names
        self.btnExperimentSetupAbort.clicked.connect(quit)
        # self.btnStartExperiment.clicked.connect(self.btnStartExperimentHandler)
        
        # self.show()

    def getAllParameters(self) -> Dict:
        return {
            "flowcell_id": self.flowcell_id,
            "experiment_name": self.experiment_name,
        }
        
class LiveviewGUI(QMainWindow):
    
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)
        self._loadUI()
        
    def _loadUI(self):
        self.setWindowTitle('Malaria Scope')
        self.setGeometry(100, 100, 1100, 700)
        # self.show()

        # Set up central layout + widget
        self.main_layout = QGridLayout()
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(self.main_layout)

        # Set up liveview layout + widget
        self.liveview_layout = QHBoxLayout()
        self.liveview_widget = QWidget()
        self.liveview_widget.setLayout(self.liveview_layout)

        # Populate liveview tab
        self.margin_layout = QVBoxLayout()
        self.margin_widget = QWidget()
        self.margin_widget.setLayout(self.margin_layout)

        # self.liveview_img = QLabel()
        self.status_lbl = QLabel("Setup")
        self.timer_lbl = QLabel("Timer")
        self.exit_btn = QPushButton("Exit")
        self.info_lbl = QLabel()
        self.hardware_lbl = QLabel()

        # self.liveview_img.setAlignment(Qt.AlignCenter)
        self.status_lbl.setAlignment(Qt.AlignHCenter)
        self.timer_lbl.setAlignment(Qt.AlignHCenter)

        self.liveview_layout.addWidget(self.margin_widget)

        self.margin_layout.addWidget(self.status_lbl)
        self.margin_layout.addWidget(self.timer_lbl)
        self.margin_layout.addWidget(self.exit_btn)
        self.margin_layout.addWidget(self.info_lbl)
        self.margin_layout.addWidget(self.hardware_lbl)

        self.main_layout.addWidget(self.liveview_widget)
        
        self.show()
        

if __name__ == "__main__":
    
    # def test():
    #     print("Start")
        
    #     i = 0
    #     while i < 3:
    #         # print(i)
    #         i += 1
    #         yield i
            
    #     return("Done")
        
    # t = test()
    # a = next(t)
    # print("OK" + str(a))
    # a = next(t)
    # print("OK" + str(a))
    # a = next(t)
    # print("OK" + str(a))
    # # next(t)
    # try:
    #     print(next(t))
    # except StopIteration as e:
    #     print(a)
    #     pass
    #     # print(e)
    # # next(t)

    app = QApplication(sys.argv)
    controller = Controller()
    # manager.show()
    sys.exit(app.exec_())