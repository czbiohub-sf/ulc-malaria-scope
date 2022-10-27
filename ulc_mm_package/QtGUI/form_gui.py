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
    QTextEdit,
    QComboBox,
)
from PyQt5.QtGui import QIcon

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
        self.operator_id_lbl = QLabel("Operator ID")
        self.participant_id_lbl = QLabel("Participant ID")
        self.flowcell_id_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Other notes")
        self.protocol_lbl = QLabel("Protocol")
        self.site_lbl = QLabel("Site")

        # Text boxes
        self.operator_id = QLineEdit()
        self.participant_id = QLineEdit()
        self.flowcell_id = QLineEdit()
        self.notes = QTextEdit()

        # Buttons
        self.exit_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.protocol = QComboBox()
        self.site = QComboBox()

        self.protocol.addItems(PROTOCOL_LIST)
        self.site.addItems(SITE_LIST)

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
        self.operator_id.setFocus()
        self.setTabOrder(self.notes, self.start_btn)

    def get_form_input(self) -> Dict:
        return {
            "operator": self.operator.text(),
            "participant": self.participant.text(),
            "flowcell": self.flowcell.text(),
            "protocol": self.protocol.currentText(),
            "site": self.site.currentText(),
            "notes": self.notes.text(),
        }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = FormGUI()
    gui.show()
    sys.exit(app.exec_())
