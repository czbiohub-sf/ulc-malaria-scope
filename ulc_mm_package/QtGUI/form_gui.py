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
from ulc_mm_package.image_processing.processing_constants import FLOWRATE
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    FLOWRATE_LIST,
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
        self.flowrate_lbl = QLabel("Flowrate")
        self.site_lbl = QLabel("Site")
        self.msg_lbl = QLabel("Hardware initializing, please wait to submit form...")

        # Text boxes
        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()
        self.flowcell_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        # Buttons
        self.exit_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.flowrate_val = QComboBox()
        self.site_val = QComboBox()

        self.flowrate_val.addItems(FLOWRATE_LIST)
        self.site_val.addItems(SITE_LIST)

        # Disable buttons at startup
        self.exit_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        # Disable text boxes at startup
        self.operator_val.setDisabled(True)
        self.participant_val.setDisabled(True)
        self.flowcell_val.setDisabled(True)
        self.notes_val.setDisabled(True)

        # Disable dropdown menus at startup
        self.flowrate_val.setDisabled(True)
        self.site_val.setDisabled(True)

        # Set tab behavior
        self.notes_val.setTabChangesFocus(True)

        # Place widgets
        self.main_layout.addWidget(self.operator_lbl, 0, 0)
        self.main_layout.addWidget(self.participant_lbl, 1, 0)
        self.main_layout.addWidget(self.flowcell_lbl, 2, 0)
        self.main_layout.addWidget(self.flowrate_lbl, 3, 0)
        self.main_layout.addWidget(self.site_lbl, 4, 0)
        self.main_layout.addWidget(self.notes_lbl, 5, 0)
        self.main_layout.addWidget(self.exit_btn, 7, 0)

        self.main_layout.addWidget(self.operator_val, 0, 1)
        self.main_layout.addWidget(self.participant_val, 1, 1)
        self.main_layout.addWidget(self.flowcell_val, 2, 1)
        self.main_layout.addWidget(self.flowrate_val, 3, 1)
        self.main_layout.addWidget(self.site_val, 4, 1)
        self.main_layout.addWidget(self.notes_val, 5, 1)
        self.main_layout.addWidget(self.start_btn, 7, 1)

        self.main_layout.addWidget(self.msg_lbl, 6, 0, 1, 2)

        # Set the focus order
        self.operator_val.setFocus()

    def unfreeze_buttons(self):
        self.msg_lbl.setText("Hardware initialized, form can now be submitted.")

        self.setTabOrder(self.notes_val, self.start_btn)

        # Enable buttons
        self.exit_btn.setEnabled(True)
        self.start_btn.setEnabled(True)

        # Enable text boxes
        self.operator_val.setDisabled(False)
        self.participant_val.setDisabled(False)
        self.flowcell_val.setDisabled(False)
        self.notes_val.setDisabled(False)

        # Enable dropdown menus
        self.flowrate_val.setDisabled(False)
        self.site_val.setDisabled(False)

    def get_form_input(self) -> dict:
        # Match keys with EXPERIMENT_METADATA_KEYS from processing_constants.py
        flowrate_name = self.flowrate_val.currentText()

        form_metadata = {
            "operator_id": self.operator_val.text(),
            "participant_id": self.participant_val.text(),
            "flowcell_id": self.flowcell_val.text(),
            "target_flowrate": (flowrate_name, FLOWRATE[flowrate_name.upper()].value),
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
