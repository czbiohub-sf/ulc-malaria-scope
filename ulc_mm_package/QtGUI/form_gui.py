"""Experiment form GUI window

Takes user input and exports experiment metadata.

"""

import sys

from PyQt6.QtCore import QRect, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
)

from ulc_mm_package.scope_constants import EXPERIMENT_METADATA_KEYS
from ulc_mm_package.image_processing.processing_constants import TARGET_FLOWRATE
from ulc_mm_package.QtGUI.gui_constants import (
    ICON_PATH,
    SITE_ENV_VAR,
    SITE_LIST,
    SAMPLE_LIST,
    TOOLBAR_OFFSET,
)
import ulc_mm_package.QtGUI.study_metadata_form as study_form


class FormGUI(QDialog):
    """Form to input experiment parameters"""

    close_event = pyqtSignal()

    def __init__(self):
        super().__init__()

        self._load_ui()

    def _study_select(self) -> None:
        text = self.study_select_val.currentText()
        if text != "":
            self.start_btn.setText("Enter additional study metadata")
        else:
            self.start_btn.setText("Start")

    def closeEvent(self, event):
        if event.spontaneous():
            self.close_event.emit()
            event.ignore()
        else:
            event.accept()

    def _load_ui(self):
        self.setWindowTitle("Experiment form")

        # Get screen parameters
        screen = QApplication.primaryScreen()
        if screen is not None:
            self.screen = screen.geometry()
            available_geometry = screen.availableGeometry()
        else:
            self.screen = QRect(0, 0, 800, 480)
            available_geometry = self.screen

        if self.screen.height() > 480:
            self.setGeometry(0, 0, 675, 500)

            # Move window to middle of screen
            window_geometry = self.frameGeometry()
            centerpoint = available_geometry.center()
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
        self.sample_id_lbl = QLabel("Non-identifying sample ID")
        self.study_select_lbl = QLabel("Select study")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.notes_lbl = QLabel("Other notes")
        self.site_lbl = QLabel("Site")
        self.sample_lbl = QLabel("Sample type")

        # Text boxes
        self.operator_val = QLineEdit()
        self.sample_id_val = QLineEdit()

        self.flowcell_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        # Buttons
        self.exit_btn = QPushButton("Exit")
        self.start_btn = QPushButton("Start")

        # Dropdown menus
        self.site_val = QComboBox()
        self.sample_val = QComboBox()
        self.study_select_val = QComboBox()
        self.study_select_val.currentTextChanged.connect(self._study_select)

        self.site_val.addItems(SITE_LIST)
        self.sample_val.addItems(SAMPLE_LIST)
        self.study_select_val.addItems(
            list(study_form.list_available_studies().keys()) + [""]
        )
        self.study_select_val.setCurrentIndex(-1)

        if SITE_ENV_VAR is not None:
            self.site_val.setEnabled(False)

        # Set tab behavior
        self.notes_val.setTabChangesFocus(True)

        # Place widgets
        self.main_layout.addWidget(self.operator_lbl, 0, 0)
        self.main_layout.addWidget(self.sample_id_lbl, 1, 0)
        self.main_layout.addWidget(self.study_select_lbl, 2, 0)
        self.main_layout.addWidget(self.flowcell_lbl, 5, 0)
        self.main_layout.addWidget(self.site_lbl, 6, 0)
        self.main_layout.addWidget(self.sample_lbl, 7, 0)
        self.main_layout.addWidget(self.notes_lbl, 8, 0)
        self.main_layout.addWidget(self.exit_btn, 9, 0)

        self.main_layout.addWidget(self.operator_val, 0, 1)
        self.main_layout.addWidget(self.sample_id_val, 1, 1)
        self.main_layout.addWidget(self.study_select_val, 2, 1)
        self.main_layout.addWidget(self.flowcell_val, 5, 1)
        self.main_layout.addWidget(self.site_val, 6, 1)
        self.main_layout.addWidget(self.sample_val, 7, 1)
        self.main_layout.addWidget(self.notes_val, 8, 1)
        self.main_layout.addWidget(self.start_btn, 9, 1)

        # Set the focus order
        self.operator_val.setFocus()
        self.start_btn.setDefault(True)

    def get_form_input(self) -> dict:
        study_name = self.study_select_val.currentText()
        if study_name != "":
            study_id = study_form.get_study_id_from_name(study_name)
        else:
            study_id = None

        form_metadata = {
            "operator_id": self.operator_val.text(),
            "sample_id": self.sample_id_val.text(),
            "flowcell_id": self.flowcell_val.text(),
            "target_flowrate": (
                TARGET_FLOWRATE.name.capitalize(),
                TARGET_FLOWRATE.value,
            ),  # fixed flowrate
            "site": self.site_val.currentText(),
            "sample_type": self.sample_val.currentText(),
            "notes": self.notes_val.toPlainText(),
            "study_id": study_id,
        }

        if not all(key in EXPERIMENT_METADATA_KEYS for key in form_metadata):
            raise KeyError("Detected invalid experiment metadata key(s)")

        return form_metadata

    def reset_parameters(self) -> None:
        """Clear specific inputs which are expected to be unique for the next run."""
        self.sample_id_val.setText("")
        self.flowcell_val.setText("")
        self.notes_val.setPlainText("")

    def sf(self) -> None:
        metadata = self.get_form_input()
        cfg = study_form.get_cfg_from_study_id(metadata["study_id"])
        if cfg is not None:
            sf = study_form.StudyMetadata(cfg, gui)
            sf.show()
        else:
            raise ValueError(f"Was unable to fetch {metadata['study_id']}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = FormGUI()
    gui.exit_btn.clicked.connect(gui.close)
    gui.start_btn.clicked.connect(gui.sf)

    print(gui.get_form_input())

    gui.show()
    sys.exit(app.exec())
