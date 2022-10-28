""" Experiment form GUI window

Takes user input and exports experiment metadata.

"""

import numpy as np
import sys

from typing import Dict

from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
)
from PyQt5.QtGui import QIcon

from ulc_mm_package.scope_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    PROTOCOL_LIST,
    SITE_LIST,
)


class FormGUI(QDialog):
    """Form to input experiment parameters"""

    def __init__(self):
        super().__init__()
        self._load_ui()

    def _load_ui(self):
        self.setWindowTitle("Experiment form")
        self.setGeometry(0, 0, 675, 500)
        self.setWindowIcon(QIcon(ICON_PATH))

        # Set up layout + widget
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        # Labels
        self.operator_lbl = QLabel("Operator ID")
        self.participant_lbl = QLabel("Participant ID")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Other notes")
        self.protocol_lbl = QLabel("Protocol")
        self.site_lbl = QLabel("Site")

        # Text boxes
        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()
        self.flowcell_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        # Buttons
        self.exit_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.protocol_val = QComboBox()
        self.site_val = QComboBox()

        self.protocol_val.addItems(PROTOCOL_LIST)
        self.site_val.addItems(SITE_LIST)

        # Place widgets
        self.main_layout.addWidget(self.operator_lbl, 0, 0)
        self.main_layout.addWidget(self.participant_lbl, 1, 0)
        self.main_layout.addWidget(self.flowcell_lbl, 2, 0)
        self.main_layout.addWidget(self.protocol_lbl, 3, 0)
        self.main_layout.addWidget(self.site_lbl, 4, 0)
        self.main_layout.addWidget(self.notes_lbl, 5, 0)
        self.main_layout.addWidget(self.exit_btn, 6, 0)

        self.main_layout.addWidget(self.operator_val, 0, 1)
        self.main_layout.addWidget(self.participant_val, 1, 1)
        self.main_layout.addWidget(self.flowcell_val, 2, 1)
        self.main_layout.addWidget(self.protocol_val, 3, 1)
        self.main_layout.addWidget(self.site_val, 4, 1)
        self.main_layout.addWidget(self.notes_val, 5, 1)
        self.main_layout.addWidget(self.start_btn, 6, 1)

        # Set the focus order
        self.operator_val.setFocus()
        self.setTabOrder(self.notes_val, self.start_btn)

    def get_form_input(self) -> dict:
        # Match keys with EXPERIMENT_METADATA_KEYS from processing_constants.py
        form_metadata = {
            "operator_id": self.operator_val.text(),
            "participant_id": self.participant_val.text(),
            "flowcell_id": self.flowcell_val.text(),
            "protocol": self.protocol_val.currentText(),
            "site": self.site_val.currentText(),
            "notes": self.notes_val.toPlainText(),
        }

        if not all(key in EXPERIMENT_METADATA_KEYS for key in form_metadata):
            raise KeyError("Detected invalid experiment metadata key(s)")

        return form_metadata


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = FormGUI()
    
    print(gui.get_form_input())

    gui.show()
    sys.exit(app.exec_())
