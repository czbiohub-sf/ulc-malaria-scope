""" Liveview GUI window

Displays camera preview and conveys info to user during runs."""

from matplotlib.streamplot import streamplot
import numpy as np
import sys

from time import perf_counter
from qimage2ndarray import gray2qimage

from PyQt5.QtWidgets import (
    QSizePolicy,
    QApplication,
    QMainWindow,
    QGridLayout,
    QHBoxLayout,
    # QVBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollBar,
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QPixmap, QIcon

from ulc_mm_package.image_processing.processing_constants import (
    TOP_PERC_TARGET_VAL,
    TARGET_FLOWRATE,
)
from ulc_mm_package.QtGUI.gui_constants import (
    STATUS,
    ICON_PATH,
    MAX_FRAMES,
)


# TEMP for testing
sample = "*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*"


class LiveviewGUI(QMainWindow):
    def __init__(self):
        self.metadata = None
        self.terminal_msg = ""

        super().__init__()
        self._load_main_ui()

    def update_experiment(self, metadata: dict):
        # TODO standardize dict input
        self.operator_val.setText(f"{metadata['operator_id']}")
        self.participant_val.setText(f"{metadata['participant_id']}")
        self.flowcell_val.setText(f"{metadata['flowcell_id']}")
        self.protocol_val.setText(f"{metadata['protocol']}")
        self.site_val.setText(f"{metadata['site']}")
        self.notes_val.setPlainText(f"{metadata['notes']}")

    @pyqtSlot(np.ndarray)
    def update_img(self, img: np.ndarray):
        self.liveview_img.setPixmap(QPixmap.fromImage(gray2qimage(img)))

    @pyqtSlot(str)
    def update_state(self, state):
        self.state_lbl.setText(state.capitalize())

        if state == "experiment":
            self._set_color(self.state_lbl, STATUS.GOOD)
        else:
            self._set_color(self.state_lbl, STATUS.IN_PROGRESS)

    @pyqtSlot(int)
    def update_img_count(self, img_count):
        self.img_count_val.setText(f"{img_count} / {MAX_FRAMES}")

    @pyqtSlot(list)
    def update_cell_count(self, cell_count):
        # TODO Check that these are mapped properly and use cleaner implementation
        self.healthy_count_val.setText(f"{cell_count[0]}")
        self.ring_count_val.setText(f"{cell_count[1]}")
        self.schizont_count_val.setText(f"{cell_count[2]}")
        self.troph_count_val.setText(f"{cell_count[3]}")

    @pyqtSlot(str)
    def update_msg(self, msg):
        self.terminal_msg = self.terminal_msg + f"{msg}\n"
        self.terminal_txt.setPlainText(self.terminal_msg)

    @pyqtSlot(int)
    def update_brightness(self, val):
        self.brightness_val.setText(f"Actual = {val}")

    @pyqtSlot(int)
    def update_focus(self, val):
        self.focus_val.setText(f"Actual = {val}")

    @pyqtSlot(int)
    def update_flowrate(self, val):
        self.flowrate_val.setText(f"Actual = {val}")

    def _set_color(self, lbl: QLabel, status: STATUS):
        lbl.setStyleSheet(f"background-color: {status.value}")

    def _load_main_ui(self):
        self.setWindowTitle("Malaria scope")
        self.setGeometry(100, 100, 1100, 700)
        self.setWindowIcon(QIcon(ICON_PATH))

        # Set up central layout + widget
        self.main_layout = QGridLayout()
        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        self.main_widget.setLayout(self.main_layout)

        self._load_infopanel_ui()
        self._load_liveview_ui()
        self._load_thumbnail_ui()
        self._load_metadata_ui()

        # Set up tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.liveview_widget, "Liveviewer")
        self.tab_widget.addTab(self.thumbnail_widget, "Parasite Thumbnails")
        self.tab_widget.addTab(self.metadata_widget, "Experiment metadata")

        # Populate window
        self.main_layout.addWidget(self.tab_widget, 0, 0)
        self.main_layout.addWidget(self.infopanel_widget, 0, 1)

    def _load_infopanel_ui(self):
        # Set up infopanel layout + widget
        self.infopanel_layout = QGridLayout()
        self.infopanel_widget = QWidget()
        self.infopanel_widget.setLayout(self.infopanel_layout)

        # Populate infopanel with general components
        self.state_lbl = QLabel("-")
        self.exit_btn = QPushButton("Exit")
        self.img_count_lbl = QLabel("Frame:")
        self.img_count_val = QLabel("-")
        self.terminal_txt = QPlainTextEdit(self.terminal_msg)
        self.terminal_scroll = QScrollBar()

        # Populate infopanel with cell counts
        self.cell_count_title = QLabel("CELL COUNTS")
        self.healthy_count_lbl = QLabel("Healthy:")
        self.ring_count_lbl = QLabel("Ring:")
        self.schizont_count_lbl = QLabel("Schizont:")
        self.troph_count_lbl = QLabel("Troph:")
        self.healthy_count_val = QLabel("-")
        self.ring_count_val = QLabel("-")
        self.schizont_count_val = QLabel("-")
        self.troph_count_val = QLabel("-")

        # Populate infopanel with routine results
        self.brightness_title = QLabel("AVERAGE BRIGHTNESS")
        self.focus_title = QLabel("FOCUS ERROR (motor steps)")
        self.flowrate_title = QLabel("CELL FLOWRATE (pix/sec)")
        self.brightness_lbl = QLabel(f"Target = {TOP_PERC_TARGET_VAL}")
        self.focus_lbl = QLabel("Target = 0")
        self.flowrate_lbl = QLabel(f"Target = {int(TARGET_FLOWRATE)}")
        self.brightness_val = QLabel("-")
        self.focus_val = QLabel("-")
        self.flowrate_val = QLabel("-")

        # Set title alignments
        self.state_lbl.setAlignment(Qt.AlignCenter)
        self.cell_count_title.setAlignment(Qt.AlignCenter)
        self.brightness_title.setAlignment(Qt.AlignCenter)
        self.focus_title.setAlignment(Qt.AlignCenter)
        self.flowrate_title.setAlignment(Qt.AlignCenter)

        # Setup terminal box
        self.terminal_txt.setReadOnly(True)

        # Setup terminal box scrollbar
        self.terminal_txt.setVerticalScrollBar(self.terminal_scroll)
        # TODO scrollbar setting doesn't work
        self.terminal_scroll.setValue(self.terminal_scroll.maximum())

        # Setup column size
        self.state_lbl.setFixedWidth(150)
        self.exit_btn.setFixedWidth(150)

        self.infopanel_layout.addWidget(self.state_lbl, 1, 1)
        self.infopanel_layout.addWidget(self.exit_btn, 1, 2)
        self.infopanel_layout.addWidget(self.img_count_lbl, 2, 1)
        self.infopanel_layout.addWidget(self.img_count_val, 2, 2)
        self.infopanel_layout.addWidget(self.terminal_txt, 14, 1, 1, 2)

        self.infopanel_layout.addWidget(self.cell_count_title, 3, 1, 1, 2)
        self.infopanel_layout.addWidget(self.healthy_count_lbl, 4, 1)
        self.infopanel_layout.addWidget(self.ring_count_lbl, 5, 1)
        self.infopanel_layout.addWidget(self.schizont_count_lbl, 6, 1)
        self.infopanel_layout.addWidget(self.troph_count_lbl, 7, 1)
        self.infopanel_layout.addWidget(self.healthy_count_val, 4, 2)
        self.infopanel_layout.addWidget(self.ring_count_val, 5, 2)
        self.infopanel_layout.addWidget(self.schizont_count_val, 6, 2)
        self.infopanel_layout.addWidget(self.troph_count_val, 7, 2)

        self.infopanel_layout.addWidget(self.brightness_title, 8, 1, 1, 2)
        self.infopanel_layout.addWidget(self.brightness_lbl, 9, 2)
        self.infopanel_layout.addWidget(self.brightness_val, 9, 1)
        self.infopanel_layout.addWidget(self.focus_title, 10, 1, 1, 2)
        self.infopanel_layout.addWidget(self.focus_lbl, 11, 2)
        self.infopanel_layout.addWidget(self.focus_val, 11, 1)
        self.infopanel_layout.addWidget(self.flowrate_title, 12, 1, 1, 2)
        self.infopanel_layout.addWidget(self.flowrate_lbl, 13, 2)
        self.infopanel_layout.addWidget(self.flowrate_val, 13, 1)

    def set_infopanel_vals(self):
        print("LIVEVIEW: Setting initial infopanel values")
        # Set label values
        self.update_img_count("---")
        self.update_cell_count(["---", "---", "---", "---"])

        self.update_brightness("---")
        self.update_focus("---")
        self.update_flowrate("---")

        # Setup status colors
        self._set_color(self.state_lbl, STATUS.IN_PROGRESS)

        self._set_color(self.cell_count_title, STATUS.STANDBY)
        self._set_color(self.brightness_title, STATUS.STANDBY)
        self._set_color(self.focus_title, STATUS.STANDBY)
        self._set_color(self.flowrate_title, STATUS.STANDBY)

        # self._set_color(self.brightness_val, STATUS.STANDBY)
        # self._set_color(self.focus_val, STATUS.STANDBY)
        # self._set_color(self.flowrate_val, STATUS.STANDBY)

    def _load_liveview_ui(self):
        # Set up liveview layout + widget
        self.liveview_layout = QHBoxLayout()
        self.liveview_widget = QWidget()
        self.liveview_widget.setLayout(self.liveview_layout)

        # Populate liveview tab
        self.liveview_img = QLabel()

        self.liveview_img.setAlignment(Qt.AlignCenter)

        self.liveview_layout.addWidget(self.liveview_img)

    def _load_thumbnail_ui(self):
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

    def _load_metadata_ui(self):
        # Set up metadata layout + widget
        self.metadata_layout = QGridLayout()
        self.metadata_widget = QWidget()
        self.metadata_widget.setLayout(self.metadata_layout)

        # Populate metadata tab
        self.operator_lbl = QLabel("Operator ID")
        self.participant_lbl = QLabel("Participant ID")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.protocol_lbl = QLabel("Protocol")
        self.site_lbl = QLabel("Site")
        self.notes_lbl = QLabel("Other notes")

        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()
        self.flowcell_val = QLineEdit()
        self.protocol_val = QLineEdit()
        self.site_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        self.operator_val.setReadOnly(True)
        self.participant_val.setReadOnly(True)
        self.flowcell_val.setReadOnly(True)
        self.protocol_val.setReadOnly(True)
        self.site_val.setReadOnly(True)
        self.notes_val.setReadOnly(True)

        self.metadata_layout.addWidget(self.operator_lbl, 1, 1)
        self.metadata_layout.addWidget(self.participant_lbl, 2, 1)
        self.metadata_layout.addWidget(self.flowcell_lbl, 3, 1)
        self.metadata_layout.addWidget(self.protocol_lbl, 4, 1)
        self.metadata_layout.addWidget(self.site_lbl, 5, 1)
        self.metadata_layout.addWidget(self.notes_lbl, 6, 1)

        self.metadata_layout.addWidget(self.operator_val, 1, 2)
        self.metadata_layout.addWidget(self.participant_val, 2, 2)
        self.metadata_layout.addWidget(self.flowcell_val, 3, 2)
        self.metadata_layout.addWidget(self.protocol_val, 4, 2)
        self.metadata_layout.addWidget(self.site_val, 5, 2)
        self.metadata_layout.addWidget(self.notes_val, 6, 2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = LiveviewGUI()

    experiment_metadata = {
        "operator_id": "1234",
        "participant_id": "567",
        "flowcell_id": "A2",
        "protocol": "Default",
        "site": "Uganda",
        "notes": sample + sample,
    }
    gui.update_experiment(experiment_metadata)

    gui.set_infopanel_vals()

    gui.show()
    sys.exit(app.exec_())
