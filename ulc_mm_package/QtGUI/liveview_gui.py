""" Liveview GUI window

Displays camera preview and conveys info to user during runs."""

import numpy as np
import sys

from qimage2ndarray import gray2qimage
from typing import Dict

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QPlainTextEdit,
    QLabel,
    QPushButton,
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QPixmap, QIcon

from ulc_mm_package.QtGUI.gui_constants import ICON_PATH


class LiveviewGUI(QMainWindow):
    def __init__(self):
        self.metadata = None

        super().__init__()
        self._load_ui()

    @pyqtSlot(np.ndarray)
    def update_img(self, img : np.ndarray):
        self.liveview_img.setPixmap(QPixmap.fromImage(gray2qimage(img)))

    def update_metadata(self, metadata : Dict):
        self.metadata = metadata 
        # TODO: Update metadata tab

    def _load_ui(self):
        self.setWindowTitle("Malaria scope")
        self.setGeometry(100, 100, 1100, 700)
        self.setWindowIcon(QIcon(ICON_PATH))

        # Set up central layout + widget
        self.main_layout = QGridLayout()
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(self.main_layout)

        # Set up margin layout + widget
        self.margin_layout = QGridLayout()
        self.margin_widget = QWidget()
        self.margin_widget.setLayout(self.margin_layout)

        # Populate margin
        self.state_lbl = QLabel("Setup")
        self.exit_btn = QPushButton("Exit")
        self.timer_lbl = QLabel("Timer")
        self.terminal_box = QPlainTextEdit("Terminal READOUT")
        self.brightness_lbl = QLabel("Brightness METRIC")
        self.focus_lbl = QLabel("Focus error METRIC")
        self.flowrate_lbl = QLabel("Flowrate METRIC")
        self.fps_lbl = QLabel("FPS")

        # Set color of metrics
        # Set size and read only of textbox

        self.margin_layout.addWidget(self.state_lbl, 1, 1)
        self.margin_layout.addWidget(self.timer_lbl, 1, 2)
        self.margin_layout.addWidget(self.exit_btn, 2, 1, 1, 2)
        self.margin_layout.addWidget(self.terminal_box, 3, 1, 3, 2)
        self.margin_layout.addWidget(self.brightness_lbl, 6, 1, 1, 2)
        self.margin_layout.addWidget(self.focus_lbl, 7, 1, 1, 2)
        self.margin_layout.addWidget(self.flowrate_lbl, 8, 1, 1, 2)
        self.margin_layout.addWidget(self.fps_lbl, 9, 1, 1, 2)

        # Set up liveview layout + widget
        self.liveview_layout = QHBoxLayout()
        self.liveview_widget = QWidget()
        self.liveview_widget.setLayout(self.liveview_layout)

        # Populate liveview tab
        self.liveview_img = QLabel()

        self.liveview_img.setAlignment(Qt.AlignCenter)
        self.state_lbl.setAlignment(Qt.AlignHCenter)
        self.timer_lbl.setAlignment(Qt.AlignHCenter)

        self.liveview_layout.addWidget(self.liveview_img)

        # Set up thumbnail layout + widget
        self.thumbnail_layout = QGridLayout()
        self.thumbnail_widget = QWidget()
        self.thumbnail_widget.setLayout(self.thumbnail_layout)

        # Populate thumbnail tab
        self.ring_lbl = QLabel("Ring")
        self.troph_lbl = QLabel("Troph")
        self.schizont_lbl = QLabel("Schizont")
        self.ring_img = QLabel()
        self.troph_img = QLabel()
        self.schizont_img = QLabel()

        self.ring_lbl.setAlignment(Qt.AlignHCenter)
        self.troph_lbl.setAlignment(Qt.AlignHCenter)
        self.schizont_lbl.setAlignment(Qt.AlignHCenter)

        self.ring_img.setScaledContents(True)
        self.troph_img.setScaledContents(True)
        self.schizont_img.setScaledContents(True)

        self.thumbnail_layout.addWidget(self.ring_lbl, 0, 0)
        self.thumbnail_layout.addWidget(self.troph_lbl, 0, 1)
        self.thumbnail_layout.addWidget(self.schizont_lbl, 0, 2)
        self.thumbnail_layout.addWidget(self.ring_img, 1, 0)
        self.thumbnail_layout.addWidget(self.troph_img, 1, 1)
        self.thumbnail_layout.addWidget(self.schizont_img, 1, 2)

        # Set up metadata layout + widget
        self.metadata_layout = QGridLayout()
        self.metadata_widget = QWidget()
        self.metadata_widget.setLayout(self.liveview_layout)

        # Populate metadata tab
        self.metadata_lbl = QLabel("Metadata here")

        self.liveview_layout.addWidget(self.metadata_lbl)

        # Set up tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.liveview_widget, "Liveviewer")
        self.tab_widget.addTab(self.thumbnail_widget, "Parasite Thumbnails")
        self.tab_widget.addTab(self.metadata_widget, "Experiment metadata")

        # Populate window
        self.main_layout.addWidget(self.tab_widget, 0, 0)
        self.main_layout.addWidget(self.margin_widget, 0, 1)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    gui = LiveviewGUI()
    gui.show()
    sys.exit(app.exec_())