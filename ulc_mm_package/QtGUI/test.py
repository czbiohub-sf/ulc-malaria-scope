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

class MalariaScopeGUI(QMainWindow, Machine):

    def __init__(self, *args, **kwargs):

        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        # Load the ui
        self._loadUI()

        self.exit_btn.clicked.connect(self.exit)



        self.kittens_rescued = 0
        states = ['asleep', 'hanging out', 'hungry', 'sweaty', 'saving the world']

        # Initialize the state machine
        self.machine = Machine(model=self, states=states, initial='asleep')

        # Add some transitions. We could also define these using a static list of
        # dictionaries, as we did with states above, and then pass the list to
        # the Machine initializer as the transitions= argument.

        # At some point, every superhero must rise and shine.
        self.machine.add_transition(trigger='wake_up', source='asleep', dest='hanging out')

        # Superheroes need to keep in shape.
        self.machine.add_transition('work_out', 'hanging out', 'hungry')

        print(self.state)
        self.wake_up()
        print(self.state)

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

    def exit(self):
        quit()

    def closeEvent(self, event):
        print("Cleaning up and exiting the application.")
        self.close()

if __name__ == "__main__":

    app = QApplication(sys.argv)
    manager = MalariaScopeGUI()
    manager.show()
    sys.exit(app.exec_())