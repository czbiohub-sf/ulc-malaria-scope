""" Liveview GUI window

Displays camera preview and conveys info to user during runs."""

import sys
from functools import partial
from typing import List, NamedTuple, Dict, Tuple
from time import strftime, gmtime

from qimage2ndarray import gray2qimage
import numpy as np

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGridLayout,
    QHBoxLayout,
    QVBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollBar,
    QDesktopWidget,
)
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon

from ulc_mm_package.image_processing.flow_control import get_flow_error

from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_CLASS_LIST,
    YOGO_CLASS_IDX_MAP,
    AF_THRESHOLD,
)
from ulc_mm_package.scope_constants import MAX_FRAMES
from ulc_mm_package.QtGUI.gui_constants import (
    STATUS,
    ICON_PATH,
    BLANK_INFOPANEL_VAL,
    TOOLBAR_OFFSET,
    MAX_THUMBNAILS,
    CLASSES_TO_DISPLAY,
    CLASS_IDS,
    MIN_THUMBNAIL_DISPLAY_SIZE,
    THUMBNAIL_SPACING,
)
from ulc_mm_package.neural_nets.YOGOInference import ClassCountResult
from ulc_mm_package.neural_nets.predictions_handler import Thumbnail


class ThumbnailDisplay(NamedTuple):
    class_name: str
    class_id: int
    list_widget: QListWidget
    list_widget_conf_labels: List[QLabel]
    list_widget_img_labels: List[QLabel]


class LiveviewGUI(QMainWindow):
    close_event = pyqtSignal()

    def __init__(self):
        self.metadata = None
        self.terminal_msg = ""
        self.target_flowrate = None

        # Get screen parameters
        self.screen = QDesktopWidget().screenGeometry()
        if self.screen.height() > 480:
            self.big_screen = True
        else:
            self.big_screen = False

        super().__init__()
        self._load_main_ui()

    def closeEvent(self, event):
        if event.spontaneous():
            self.close_event.emit()
            event.ignore()
        else:
            event.accept()

    def update_experiment(self, metadata: dict):
        # TODO standardize dict input
        self.operator_val.setText(f"{metadata['operator_id']}")
        self.participant_val.setText(f"{metadata['participant_id']}")
        self.flowcell_val.setText(f"{metadata['flowcell_id']}")
        self.target_flowrate_val.setText(f"{metadata['target_flowrate'][0]}")
        self.site_val.setText(f"{metadata['site']}")
        self.notes_val.setPlainText(f"{metadata['notes']}")

        # Update target flowrate in infopanel
        self.target_flowrate = metadata["target_flowrate"][1]
        self.flowrate_lbl.setText(f"Target = {self.target_flowrate}")

    def update_tcp(self, tcp_addr):
        self.tcp_lbl.setText(f"SSH: {tcp_addr}")

    @pyqtSlot(float)
    def update_runtime(self, runtime):
        self.runtime_val.setText(strftime("%M:%S", gmtime(runtime)))

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

    @pyqtSlot(ClassCountResult)
    def update_cell_count(self, cell_count: ClassCountResult):
        healthy_cell_count = cell_count[YOGO_CLASS_IDX_MAP["healthy"]]
        ring_cell_count = cell_count[YOGO_CLASS_IDX_MAP["ring"]]
        schiz_cell_count = cell_count[YOGO_CLASS_IDX_MAP["schizont"]]
        troph_cell_count = cell_count[YOGO_CLASS_IDX_MAP["troph"]]

        # 'x or y' syntax means 'x if x is "truthy" else y'
        # x is "truthy" if bool(x) == True
        # so in this case, if the cell count == 0, bool(0) == False,
        # so we get string '---'
        healthy_count_str = f"{healthy_cell_count or '---'}"
        ring_count_str = f"{ring_cell_count or '---'}"
        schiz_count_str = f"{schiz_cell_count or '---'}"
        troph_count_str = f"{troph_cell_count or '---'}"

        self.healthy_count_val.setText(healthy_count_str)
        self.ring_count_val.setText(ring_count_str)
        self.schizont_count_val.setText(schiz_count_str)
        self.troph_count_val.setText(troph_count_str)

    @pyqtSlot(str)
    def update_msg(self, msg):
        if self.big_screen:
            self.terminal_msg = self.terminal_msg + f"{msg}\n"
            self.msg_lbl.setPlainText(self.terminal_msg)

            # Scroll to latest message
            self.terminal_scroll.setValue(self.terminal_scroll.maximum())

    @pyqtSlot(float)
    def update_focus(self, val):
        self.focus_val.setText(
            f"Actual = {val:.2f}" if isinstance(val, float) else f"Actual = {val}"
        )

        # Set color based on status
        if isinstance(val, float):
            if abs(val) > AF_THRESHOLD:
                self._set_color(self.focus_val, STATUS.BAD)
            else:
                self._set_color(self.focus_val, STATUS.GOOD)
        else:
            self._set_color(self.focus_val, STATUS.DEFAULT)

    @pyqtSlot(float)
    def update_flowrate(self, val):
        self.flowrate_val.setText(
            f"Actual = {val:.2f}" if isinstance(val, float) else f"Actual = {val}"
        )

        # Set color based on status
        if (self.target_flowrate is not None) and isinstance(val, (float, int)):
            if get_flow_error(self.target_flowrate, val) == 0:
                self._set_color(self.flowrate_val, STATUS.GOOD)
            else:
                self._set_color(self.flowrate_val, STATUS.BAD)
        else:
            self._set_color(self.flowrate_val, STATUS.DEFAULT)

    @pyqtSlot(object)
    def update_thumbnails(
        self,
        tuple_of_dict_of_thumbnails: Tuple[
            Dict[int, List[Thumbnail]], Dict[int, List[Thumbnail]]
        ],
    ):
        max_confs = tuple_of_dict_of_thumbnails[0]
        min_confs = tuple_of_dict_of_thumbnails[1]

        max_conf_display = self.max_and_min_conf_thumbnail_displays["max_conf"]
        min_conf_display = self.max_and_min_conf_thumbnail_displays["min_conf"]

        for i in CLASS_IDS:
            max_conf_thumbnails = max_confs[i]
            min_conf_thumbnails = min_confs[i]
            max_display_for_i = max_conf_display[
                i
            ]  # row corresponding to this class id
            min_display_for_i = min_conf_display[i]

            for j, (t_max, t_min) in enumerate(
                zip(max_conf_thumbnails, min_conf_thumbnails)
            ):
                # Set confidence labels
                max_display_for_i.list_widget_conf_labels[j].setText(
                    f"{t_max.confidence:.3f}"
                )
                min_display_for_i.list_widget_conf_labels[j].setText(
                    f"{t_min.confidence:.3f}"
                )

                # Set thumbnail
                max_display_for_i.list_widget_img_labels[j].setPixmap(
                    QPixmap.fromImage(gray2qimage(t_max.img_crop))
                )
                min_display_for_i.list_widget_img_labels[j].setPixmap(
                    QPixmap.fromImage(gray2qimage(t_min.img_crop))
                )

                # qs_max = self._get_qsize(*t_max.img_crop.shape)
                # qs_min = self._get_qsize(*t_min.img_crop.shape)
                # max_display_for_i.list_widget.item(j).setSizeHint(qs_max)
                # min_display_for_i.list_widget.item(j).setSizeHint(qs_min)

    def _get_qsize(self, h, w):
        qs = QSize()
        qs.setHeight(h)
        qs.setWidth(w)
        return qs

    def _set_color(self, lbl: QLabel, status: STATUS):
        lbl.setStyleSheet(f"background-color: {status.value}")

    def _load_main_ui(self):
        self.setWindowTitle("Malaria scope")
        self.setGeometry(
            self.screen.x(),
            self.screen.y(),
            self.screen.width(),
            self.screen.height() - TOOLBAR_OFFSET,
        )
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
        self.pause_btn = QPushButton("Pause")
        self.exit_btn = QPushButton("Exit")
        self.runtime_lbl = QLabel("Runtime:")
        self.runtime_val = QLabel("-")
        self.img_count_lbl = QLabel("Fields of view:")
        self.img_count_val = QLabel("-")
        self.terminal_scroll = QScrollBar()
        self.tcp_lbl = QLabel("-")

        # Set up message terminal
        if self.big_screen:
            self.msg_lbl = QPlainTextEdit(self.terminal_msg)
            self.msg_lbl.setReadOnly(True)
            self.msg_lbl.setVerticalScrollBar(self.terminal_scroll)

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
        self.focus_title = QLabel("FOCUS ERROR (motor steps)")
        self.flowrate_title = QLabel("CELL FLOWRATE (FoVs/sec)")
        self.focus_lbl = QLabel("Target = 0")
        self.flowrate_lbl = QLabel("Target = -")
        self.focus_val = QLabel("-")
        self.flowrate_val = QLabel("-")

        # Set title alignments
        self.state_lbl.setAlignment(Qt.AlignCenter)
        self.cell_count_title.setAlignment(Qt.AlignCenter)
        self.focus_title.setAlignment(Qt.AlignCenter)
        self.flowrate_title.setAlignment(Qt.AlignCenter)
        self.tcp_lbl.setAlignment(Qt.AlignCenter)

        # Setup column size
        self.pause_btn.setFixedWidth(120)
        self.exit_btn.setFixedWidth(120)

        self.infopanel_layout.addWidget(self.state_lbl, 0, 1, 1, 2)
        self.infopanel_layout.addWidget(self.pause_btn, 1, 1)
        self.infopanel_layout.addWidget(self.exit_btn, 1, 2)
        self.infopanel_layout.addWidget(self.runtime_lbl, 2, 1)
        self.infopanel_layout.addWidget(self.runtime_val, 2, 2)
        self.infopanel_layout.addWidget(self.img_count_lbl, 3, 1)
        self.infopanel_layout.addWidget(self.img_count_val, 3, 2)
        if self.big_screen:
            self.infopanel_layout.addWidget(self.msg_lbl, 14, 1, 1, 2)
        self.infopanel_layout.addWidget(self.tcp_lbl, 15, 1, 1, 2)

        self.infopanel_layout.addWidget(self.cell_count_title, 4, 1, 1, 2)
        self.infopanel_layout.addWidget(self.ring_count_lbl, 6, 1)
        self.infopanel_layout.addWidget(self.ring_count_val, 6, 2)
        self.infopanel_layout.addWidget(self.healthy_count_lbl, 5, 1)
        self.infopanel_layout.addWidget(self.healthy_count_val, 5, 2)
        self.infopanel_layout.addWidget(self.schizont_count_lbl, 7, 1)
        self.infopanel_layout.addWidget(self.schizont_count_val, 7, 2)
        self.infopanel_layout.addWidget(self.troph_count_lbl, 8, 1)
        self.infopanel_layout.addWidget(self.troph_count_val, 8, 2)

        self.infopanel_layout.addWidget(self.focus_title, 10, 1, 1, 2)
        self.infopanel_layout.addWidget(self.focus_lbl, 11, 2)
        self.infopanel_layout.addWidget(self.focus_val, 11, 1)
        self.infopanel_layout.addWidget(self.flowrate_title, 12, 1, 1, 2)
        self.infopanel_layout.addWidget(self.flowrate_lbl, 13, 2)
        self.infopanel_layout.addWidget(self.flowrate_val, 13, 1)

    def set_infopanel_vals(self):
        # Flush terminal
        self.terminal_msg = ""
        if self.big_screen:
            self.msg_lbl.clear()

        self.update_runtime(0)
        self.update_img_count(BLANK_INFOPANEL_VAL)
        self.update_cell_count(np.zeros(len(YOGO_CLASS_LIST), dtype=int))

        self.update_focus(BLANK_INFOPANEL_VAL)
        self.update_flowrate(BLANK_INFOPANEL_VAL)

        # Setup status colors
        self._set_color(self.state_lbl, STATUS.IN_PROGRESS)

        self._set_color(self.cell_count_title, STATUS.STANDBY)
        self._set_color(self.focus_title, STATUS.STANDBY)
        self._set_color(self.flowrate_title, STATUS.STANDBY)

        self._set_color(self.focus_val, STATUS.DEFAULT)
        self._set_color(self.flowrate_val, STATUS.DEFAULT)

        self._set_color(self.tcp_lbl, STATUS.STANDBY)

    def _load_liveview_ui(self):
        # Set up liveview layout + widget
        self.liveview_layout = QHBoxLayout()
        self.liveview_widget = QWidget()
        self.liveview_widget.setLayout(self.liveview_layout)

        # Populate liveview tab
        self.liveview_img = QLabel()

        self.liveview_img.setAlignment(Qt.AlignCenter)
        self.liveview_img.setMinimumSize(1, 1)
        self.liveview_img.setScaledContents(True)

        self.liveview_layout.addWidget(self.liveview_img)

    def _load_thumbnail_ui(self):
        # Set up thumbnail layout + widget
        self.thumbnail_layout = QGridLayout()
        self.thumbnail_widget = QWidget()
        self.thumbnail_widget.setLayout(self.thumbnail_layout)

        # Populate thumbnail tab
        class_labels = [QLabel(c) for c in CLASSES_TO_DISPLAY]
        [label.setAlignment(Qt.AlignVCenter) for label in class_labels]

        self.max_and_min_conf_thumbnail_displays: Dict[str, List[ThumbnailDisplay]] = {
            "max_conf": [],
            "min_conf": [],
        }
        for k in self.max_and_min_conf_thumbnail_displays.keys():
            thumbnail_lists: List[ThumbnailDisplay] = []
            for i, c in enumerate(CLASSES_TO_DISPLAY):
                class_id = CLASS_IDS[i]
                class_name = c
                conf_labels: List[QLabel] = []
                img_labels: List[QLabel] = []

                list_widget = QListWidget()
                list_widget.setFlow(QListView.LeftToRight)
                list_widget.setContentsMargins(0, 0, 0, 0)

                for i in range(MAX_THUMBNAILS):
                    w = QWidget()
                    layout = QVBoxLayout()
                    layout.setSpacing(0)
                    layout.setContentsMargins(
                        THUMBNAIL_SPACING, 0, THUMBNAIL_SPACING, 0
                    )

                    conf_label = QLabel()
                    conf_label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)

                    img_label = QLabel()
                    conf_labels.append(conf_label)
                    img_labels.append(img_label)

                    layout.addWidget(conf_label)
                    layout.addWidget(img_label)
                    layout.setAlignment(Qt.AlignVCenter)
                    w.setLayout(layout)

                    v = QListWidgetItem()
                    v.setFlags(Qt.NoItemFlags)
                    qs = QSize()
                    qs.setHeight(MIN_THUMBNAIL_DISPLAY_SIZE)
                    qs.setWidth(MIN_THUMBNAIL_DISPLAY_SIZE)
                    v.setSizeHint(qs)
                    list_widget.addItem(v)
                    list_widget.setItemWidget(v, w)

                thumbnail_lists.append(
                    ThumbnailDisplay(
                        class_name=class_name,
                        class_id=class_id,
                        list_widget=list_widget,
                        list_widget_conf_labels=conf_labels,
                        list_widget_img_labels=img_labels,
                    )
                )
                self.max_and_min_conf_thumbnail_displays[k] = thumbnail_lists

        self.refresh_thumbnails = QPushButton("Click to refresh thumbnails")
        self.toggle_confs = QPushButton("Click to display min confidence thumbnails")
        self.toggle_confs.setCheckable(True)
        self.toggle_confs.clicked.connect(self.toggle_thumbnails)

        self.thumbnail_layout.addWidget(self.refresh_thumbnails, 0, 0)
        self.thumbnail_layout.addWidget(self.toggle_confs, 0, 1)

        # Class labels
        [
            self.thumbnail_layout.addWidget(label, i + 1, 0)
            for i, label in enumerate(class_labels)
        ]

        for k in self.max_and_min_conf_thumbnail_displays.keys():
            thumbnail_lists = self.max_and_min_conf_thumbnail_displays[k]
            for i, x in enumerate(thumbnail_lists):
                if k == "min_conf":
                    x.list_widget.setVisible(False)
                self.thumbnail_layout.addWidget(x.list_widget, i + 1, 1)

            # Synchronize scrollbars
            sbars = [x.list_widget.horizontalScrollBar() for x in thumbnail_lists]

            for i, x in enumerate(thumbnail_lists):
                [
                    x.list_widget.horizontalScrollBar().valueChanged.connect(
                        partial(self.move_scrollbar, s)
                    )
                    for j, s in enumerate(sbars)
                    if j != i
                ]
            [x.list_widget.horizontalScrollBar().hide() for x in thumbnail_lists[1:]]

        # self.thumbnail_layout.addWidget(self.toggle_confs, len(CLASSES_TO_DISPLAY), 1)

    def move_scrollbar(self, vs, value):
        vs.setValue(value)

    def toggle_thumbnails(self):
        if not self.toggle_confs.isChecked():
            self.toggle_confs.setText("Click to display min confidence thumbnails")
            for x in self.max_and_min_conf_thumbnail_displays["min_conf"]:
                x.list_widget.setVisible(False)
            for x in self.max_and_min_conf_thumbnail_displays["max_conf"]:
                x.list_widget.setVisible(True)
        else:
            self.toggle_confs.setText("Click to display max confidence thumbnails")
            for x in self.max_and_min_conf_thumbnail_displays["min_conf"]:
                x.list_widget.setVisible(True)
            for x in self.max_and_min_conf_thumbnail_displays["max_conf"]:
                x.list_widget.setVisible(False)

    def _load_metadata_ui(self):
        # Set up metadata layout + widget
        self.metadata_layout = QGridLayout()
        self.metadata_widget = QWidget()
        self.metadata_widget.setLayout(self.metadata_layout)

        # Populate metadata tab
        self.operator_lbl = QLabel("Operator ID")
        self.participant_lbl = QLabel("Participant ID")
        self.flowcell_lbl = QLabel("Flowcell ID")
        self.target_flowrate_lbl = QLabel("Flowrate")
        self.site_lbl = QLabel("Site")
        self.notes_lbl = QLabel("Other notes")

        self.operator_val = QLineEdit()
        self.participant_val = QLineEdit()
        self.flowcell_val = QLineEdit()
        self.target_flowrate_val = QLineEdit()
        self.site_val = QLineEdit()
        self.notes_val = QPlainTextEdit()

        self.operator_val.setReadOnly(True)
        self.participant_val.setReadOnly(True)
        self.flowcell_val.setReadOnly(True)
        self.target_flowrate_val.setReadOnly(True)
        self.site_val.setReadOnly(True)
        self.notes_val.setReadOnly(True)

        self.metadata_layout.addWidget(self.operator_lbl, 1, 1)
        self.metadata_layout.addWidget(self.participant_lbl, 2, 1)
        self.metadata_layout.addWidget(self.flowcell_lbl, 3, 1)
        self.metadata_layout.addWidget(self.target_flowrate_lbl, 4, 1)
        self.metadata_layout.addWidget(self.site_lbl, 5, 1)
        self.metadata_layout.addWidget(self.notes_lbl, 6, 1)

        self.metadata_layout.addWidget(self.operator_val, 1, 2)
        self.metadata_layout.addWidget(self.participant_val, 2, 2)
        self.metadata_layout.addWidget(self.flowcell_val, 3, 2)
        self.metadata_layout.addWidget(self.target_flowrate_val, 4, 2)
        self.metadata_layout.addWidget(self.site_val, 5, 2)
        self.metadata_layout.addWidget(self.notes_val, 6, 2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = LiveviewGUI()

    experiment_metadata = {
        "operator_id": "1234",
        "participant_id": "567",
        "flowcell_id": "A2",
        "target_flowrate": ("Fast", 15),
        "site": "Uganda",
        "notes": "*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*\n*",
    }
    gui.update_experiment(experiment_metadata)

    gui.set_infopanel_vals()
    print(gui.screen)

    gui.update_msg("Sample message here")
    gui.update_tcp("Sample address here")

    gui.showMaximized()
    gui.exit_btn.clicked.connect(gui.close)
    sys.exit(app.exec_())
