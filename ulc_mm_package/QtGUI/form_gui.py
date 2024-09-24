""" Experiment form GUI window

Takes user input and exports experiment metadata.

"""

import sys


from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QDesktopWidget,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt

from ulc_mm_package.scope_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    SITE_LIST,
    SAMPLE_LIST,
    TOOLBAR_OFFSET,
)


class FormGUI(QDialog):
    """Form to input experiment parameters"""

    close_event = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._load_ui()

    def closeEvent(self, event):
        if event.spontaneous():
            self.close_event.emit()
            event.ignore()
        else:
            event.accept()

    def _load_ui(self):
        self.setWindowTitle("Experiment form")

        # Get screen parameters
        self.screen = QDesktopWidget().screenGeometry()
        if self.screen.height() > 480:
            self.setGeometry(0, 0, 675, 500)

            # Move window to middle of screen
            window_geometry = self.frameGeometry()
            centerpoint = QDesktopWidget().availableGeometry().center()
            window_geometry.moveCenter(centerpoint)
            self.move(window_geometry.topLeft())
        else:
            self.setGeometry(
                self.screen.x(),
                self.screen.y(),
                self.screen.width(),
                self.screen.height() - TOOLBAR_OFFSET,
            )

        self.setWindowIcon(QIcon(ICON_PATH))

        # Set up layout + widget
        self.main_layout = QGridLayout()
        self.setLayout(self.main_layout)

        # Labels
        self.operator_lbl = QLabel("Operator ID")
        self.participant_lbl = QLabel("Non-identifying participant ID")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Other notes")
        self.site_lbl = QLabel("Site")
        self.sample_lbl = QLabel("Sample type")
        self.msg_lbl = QLabel("Hardware initializing, please wait to submit form...")

        # Text boxes
        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()
        self.flowcell_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        # Buttons
        self.exit_btn = QPushButton("Exit")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.site_val = QComboBox()
        self.sample_val = QComboBox()

        self.site_val.addItems(SITE_LIST)
        self.sample_val.addItems(SAMPLE_LIST)

        # Disable buttons at startup
        self.exit_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        # Disable [x] button at startup
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        # Disable text boxes at startup
        self.operator_val.setDisabled(True)
        self.participant_val.setDisabled(True)
        self.flowcell_val.setDisabled(True)
        self.notes_val.setDisabled(True)

        # Disable dropdown menus at startup
        self.site_val.setDisabled(True)
        self.sample_val.setDisabled(True)

        # Set tab behavior
        self.notes_val.setTabChangesFocus(True)

        # Place widgets
        self.main_layout.addWidget(self.operator_lbl, 0, 0)
        self.main_layout.addWidget(self.participant_lbl, 1, 0)
        self.main_layout.addWidget(self.flowcell_lbl, 2, 0)
        self.main_layout.addWidget(self.site_lbl, 4, 0)
        self.main_layout.addWidget(self.sample_lbl, 5, 0)
        self.main_layout.addWidget(self.notes_lbl, 6, 0)
        self.main_layout.addWidget(self.exit_btn, 8, 0)

        self.main_layout.addWidget(self.operator_val, 0, 1)
        self.main_layout.addWidget(self.participant_val, 1, 1)
        self.main_layout.addWidget(self.flowcell_val, 2, 1)
        self.main_layout.addWidget(self.site_val, 4, 1)
        self.main_layout.addWidget(self.sample_val, 5, 1)
        self.main_layout.addWidget(self.notes_val, 6, 1)
        self.main_layout.addWidget(self.start_btn, 8, 1)

        self.main_layout.addWidget(self.msg_lbl, 7, 0, 1, 2)

        # Set the focus order
        self.operator_val.setFocus()
        self.start_btn.setDefault(True)

    def unfreeze_buttons(self):
        self.msg_lbl.setText("Hardware initialized, form can now be submitted.")

        self.setTabOrder(self.notes_val, self.start_btn)

        # Enable buttons
        self.exit_btn.setEnabled(True)
        self.start_btn.setEnabled(True)

        # Enable [x] button
        self.setWindowFlag(Qt.WindowCloseButtonHint, True)

        # Enable dropdown menus
        self.site_val.setEnabled(True)
        self.sample_val.setEnabled(True)

        # Enable text boxes
        self.operator_val.setEnabled(True)
        self.participant_val.setEnabled(True)
        self.flowcell_val.setEnabled(True)
        self.notes_val.setEnabled(True)

    def get_form_input(self) -> dict:
        form_metadata = {
            "operator_id": self.operator_val.text(),
            "participant_id": self.participant_val.text(),
            "flowcell_id": self.flowcell_val.text(),
            "target_flowrate": (
                TARGET_FLOWRATE.name.capitalize(),
                TARGET_FLOWRATE.value,
            ),  # fixed flowrate
            "site": self.site_val.currentText(),
            "sample_type": self.sample_val.currentText(),
            "notes": self.notes_val.toPlainText(),
        }

        if not all(key in EXPERIMENT_METADATA_KEYS for key in form_metadata):
            raise KeyError("Detected invalid experiment metadata key(s)")

        return form_metadata

    def reset_parameters(self) -> None:
        """Clear specific inputs which are expected to be unique for the next run."""
        self.participant_val.setText("")
        self.flowcell_val.setText("")
        self.notes_val.setPlainText("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = FormGUI()

    print(gui.get_form_input())

    gui.show()
    sys.exit(app.exec_())
