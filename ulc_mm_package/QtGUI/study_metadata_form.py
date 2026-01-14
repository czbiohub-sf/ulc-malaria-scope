from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QIntValidator
from PyQt5.QtGui import QDoubleValidator

from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDateEdit,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
import tomli

DATATYPE_TO_WIDGET = {
    "string": "lineedit",
    "int": "spinbox",
    "float": "doublespinbox",
    "date": "dateedit",
    "enum": "combobox",
    "bool": "combobox",
    "multiselect": "listwidget",
}


def create_widget_for_field(field_def):
    t = field_def["datatype"]

    if t == "string" and field_def.get("multiline"):
        w = QTextEdit()
        w.setTabChangesFocus(True)
    elif t == "string":
        w = QLineEdit()
        if "max_length" in field_def:
            w.setMaxLength(field_def["max_length"])
        if "placeholder" in field_def:
            w.setPlaceholderText(field_def["placeholder"])
    elif t == "int":
        w = QLineEdit()
        if "min" in field_def and "max" in field_def:
            validator = QIntValidator(field_def["min"], field_def["max"])
        elif "min" in field_def:
            # large upper bound if only min provided
            validator = QIntValidator(field_def["min"], 2**31 - 1)
        elif "max" in field_def:
            validator = QIntValidator(-(2**31), field_def["max"])
        else:
            validator = QIntValidator()
        w.setValidator(validator)

    elif t == "float":
        w = QLineEdit()
        if "min" in field_def and "max" in field_def:
            validator = QDoubleValidator(field_def["min"], field_def["max"], 10)
        elif "min" in field_def:
            validator = QDoubleValidator(field_def["min"], 1e308, 10)
        elif "max" in field_def:
            validator = QDoubleValidator(-1e308, field_def["max"], 10)
        else:
            validator = QDoubleValidator()
        validator.setNotation(QDoubleValidator.StandardNotation)
        w.setValidator(validator)

    elif t == "date":
        w = QDateEdit()
        w.setDisplayFormat("yyyy-MM-dd")
        w.setDate(QDate.currentDate())
        w.setCalendarPopup(True)

    elif t == "enum":
        w = QComboBox()
        for choice in field_def.get("choices", []):
            w.addItem(choice)
        w.setCurrentIndex(-1)

        default = field_def.get("default")
        if default is not None:
            print("default is")
            idx = w.findText(default)
            if idx >= 0:
                w.setCurrentIndex(idx)
    elif t == "bool":
        w = QComboBox()
        w.addItem("True", True)
        w.addItem("False", False)
        w.addItem("None", None)
        w.setCurrentIndex(-1)
    elif t == "multiselect":
        w = QListWidget()
        for choice in field_def.get("choices", []):
            w.addItem(choice)
        w.setSelectionMode(QAbstractItemView.MultiSelection)
    else:
        raise ValueError(f"Unsupported field type: {t}")

    return w


class StudyMetadata(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)

        # Container for scrolling
        outer_scroll_container = QVBoxLayout(self)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        container = QWidget()
        layout = QFormLayout(container)

        self.config_data = cfg
        metadata = self.config_data["metadata"]
        self._widgets = {}
        self._required_widgets: List[QWidget] = []

        # Confirmation buttons
        btn_cancel = QPushButton("Cancel")
        self.btn_start = QPushButton("Start experiment")
        self.btn_start.setDefault(True)

        for field in metadata:
            label = field.get("label")

            if label is None:
                raise ValueError(f"Missing label for {field}")

            widget = create_widget_for_field(field)
            self._widgets[field["label"]] = (widget, field)
            if field.get("required") is True:
                self._required_widgets.append(widget)
                self.btn_start.setEnabled(False)
            layout.addRow(label, widget)

        self.btn_start.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.close)

        layout.addRow(btn_cancel, self.btn_start)
        scroller.setWidget(container)
        outer_scroll_container.addWidget(scroller)

        # For the required widgets, deal with each widget's different value changed functions
        for w in self._required_widgets:
            if hasattr(w, "textChanged"):
                w.textChanged.connect(lambda *_: self.check_required())
            elif hasattr(w, "currentTextChanged"):
                w.currentTextChanged.connect(lambda *_: self.check_required())
            elif hasattr(w, "currentIndexChanged"):
                w.currentIndexChanged.connect(lambda *_: self.check_required())
            elif hasattr(w, "valueChanged"):
                w.valueChanged.connect(lambda *_: self.check_required())
            elif hasattr(w, "dateChanged"):
                w.dateChanged.connect(lambda *_: self.check_required())

        # run an initial check to set OK button state
        self.check_required()

    def check_required(self):
        """Ensure that all required widgets have a value."""
        all_filled = True
        for w in self._required_widgets:
            if hasattr(w, "toPlainText"):
                if not w.toPlainText().strip():
                    all_filled = False
                    break
            elif hasattr(w, "text"):
                if not w.text().strip():
                    all_filled = False
                    break
            elif hasattr(w, "currentIndex"):
                # -1 index means no selection made
                if w.currentIndex() < 0:
                    all_filled = False
                    break
        if all_filled:
            self.btn_start.setEnabled(True)
            self.btn_start.setFocus(True)
        else:
            self.btn_start.setEnabled(False)

    def get_form_input(self):
        result = {"study_id": self.config_data["study_description"]["key"]}
        errors = []
        for name, (widget, field) in self._widgets.items():
            t = field["datatype"]

            if t == "string":
                value = (
                    widget.toPlainText() if field.get("multiline") else widget.text()
                )
            elif t == "int":
                text = widget.text().strip()
                value = None if not text else int(widget.text())
            elif t == "float":
                text = widget.text().strip()
                value = None if not text else float(widget.text())
            elif t == "date":
                qd = widget.date()
                value = qd.toString("yyyy-MM-dd")
            elif t == "enum":
                value = widget.currentText()
            elif t == "bool":
                value = widget.currentData()
            else:
                value = None

            result[name] = value

        if errors:
            raise ValueError("\n".join(errors))

        return result


def _load(path: Path) -> Dict:
    with open(path, "rb") as f:
        config = tomli.load(f)
    return config


def list_available_studies() -> Dict[str, dict]:
    """List the available studies (those .toml files stored in study_configurations/).
    Note if a file is prepended with `_`, it will be ignored.

    Returns
    -------
    A dictionary mapping the study name (as defined in its toml file) to its parsed dictionary.
    """
    study_config_dir = Path(__file__).resolve().parent.parent / "study_configurations"
    possible_studies = list(study_config_dir.parent.rglob("*.toml"))
    valid_studies = [x for x in possible_studies if x.stem[0] != "_"]

    study_name_to_metadata: dict = {}
    for study_path in valid_studies:
        cfg = _load(study_path)
        study_name_to_metadata[cfg["study_description"]["name"]] = cfg

    return study_name_to_metadata


def get_cfg_from_study_id(study_id: str) -> Optional[Dict]:
    if study_id == "" or study_id is None:
        return None
    studies = list_available_studies()
    for study in studies:
        cfg_study_id = studies[study]["study_description"]["key"]
        if study_id == cfg_study_id:
            return studies[study]
    else:
        raise ValueError(f"No matching study found for {study_id}")


def get_study_id_from_name(study_name: str) -> str:
    return list_available_studies()[study_name]["study_description"]["key"]
