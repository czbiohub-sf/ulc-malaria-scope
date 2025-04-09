"""Experiment form GUI window

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
from PyQt5.QtCore import pyqtSignal, QDate, QTime

from ulc_mm_package.scope_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE
from PyQt5.QtWidgets import QDateEdit, QTimeEdit
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

    def _validate_temperature(self):
        text = self.sample_storage_temp.text()
        if not text.endswith(("C", "F", "c", "f")) or not text[:-1].isdigit():
            self.sample_storage_temp.setStyleSheet("border: 1px solid red;")
            self.start_btn.setEnabled(False)
        else:
            self.sample_storage_temp.setStyleSheet("")
            self.start_btn.setEnabled(True)

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
        self.sample_collection_date_lbl = QLabel("Sample collection date")
        self.sample_collection_time_lbl = QLabel("Sample collection time")
        self.sample_storage_temp_lbl = QLabel("Sample storage temperature (°C or °F)")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Other notes")
        self.site_lbl = QLabel("Site")
        self.sample_lbl = QLabel("Sample type")
        self.msg_lbl = QLabel("Please fill out experiment data.")

        # Text boxes
        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()

        # Sample collection date
        self.sample_collection_date = QDateEdit(QDate.currentDate())
        self.sample_collection_date.setCalendarPopup(True)
        self.sample_collection_date.setDisplayFormat("yyyy-MMM-dd")

        # Sample collection time
        self.sample_collection_time = QTimeEdit(QTime.currentTime())
        self.sample_collection_time.setDisplayFormat("hh:mm AP")
        self.sample_collection_time.setCalendarPopup(True)

        # Sample storage temperature
        self.sample_storage_temp = QLineEdit()
        self.sample_storage_temp.setPlaceholderText(
            "Enter temperature (e.g. 25C or 77F)"
        )
        self.sample_storage_temp.textChanged.connect(self._validate_temperature)

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

        # Set tab behavior
        self.notes_val.setTabChangesFocus(True)

        # Place widgets
        self.main_layout.addWidget(self.operator_lbl, 0, 0)
        self.main_layout.addWidget(self.participant_lbl, 1, 0)
        self.main_layout.addWidget(self.sample_collection_date_lbl, 2, 0)
        self.main_layout.addWidget(self.sample_collection_time_lbl, 3, 0)
        self.main_layout.addWidget(self.sample_storage_temp_lbl, 4, 0)
        self.main_layout.addWidget(self.flowcell_lbl, 5, 0)
        self.main_layout.addWidget(self.site_lbl, 6, 0)
        self.main_layout.addWidget(self.sample_lbl, 7, 0)
        self.main_layout.addWidget(self.notes_lbl, 8, 0)
        self.main_layout.addWidget(self.exit_btn, 9, 0)

        self.main_layout.addWidget(self.operator_val, 0, 1)
        self.main_layout.addWidget(self.participant_val, 1, 1)
        self.main_layout.addWidget(self.sample_collection_date, 2, 1)
        self.main_layout.addWidget(self.sample_collection_time, 3, 1)
        self.main_layout.addWidget(self.sample_storage_temp, 4, 1)
        self.main_layout.addWidget(self.flowcell_val, 5, 1)
        self.main_layout.addWidget(self.site_val, 6, 1)
        self.main_layout.addWidget(self.sample_val, 7, 1)
        self.main_layout.addWidget(self.notes_val, 8, 1)
        self.main_layout.addWidget(self.start_btn, 9, 1)

        self.main_layout.addWidget(self.msg_lbl, 10, 0, 1, 2)

        # Set the focus order
        self.operator_val.setFocus()
        self.start_btn.setDefault(True)

    def get_form_input(self) -> dict:
        # Determine the sample age from the current time and the sample collection time
        current_date = QDate.currentDate()
        current_time = QTime.currentTime()

        sample_date = self.sample_collection_date.date()
        sample_time = self.sample_collection_time.time()

        date_diff_in_hours = sample_date.daysTo(current_date) * 24
        time_diff_in_hours = sample_time.secsTo(current_time) / 3600

        sample_age_hours = round(date_diff_in_hours + time_diff_in_hours, 2)

        form_metadata = {
            "operator_id": self.operator_val.text(),
            "participant_id": self.participant_val.text(),
            "flowcell_id": self.flowcell_val.text(),
            "sample_collection_date": self.sample_collection_date.text(),
            "sample_collection_time": self.sample_collection_time.text(),
            "sample_age_hours": sample_age_hours,
            "sample_storage_temp": self.sample_storage_temp.text(),
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
    gui.exit_btn.clicked.connect(gui.close)

    print(gui.get_form_input())

    gui.show()
    sys.exit(app.exec_())
