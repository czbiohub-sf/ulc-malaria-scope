""" Image manager

Receives images from the camera and sends them to Liveview and ScopeOp.

"""

import logging
import traceback
import numpy as np

from time import perf_counter, sleep
from PyQt5.QtCore import (
    QObject,
    QTimer,
    pyqtSignal,
    pyqtSlot,
    Qt,
)

from py_cameras import PyCamerasError

from ulc_mm_package.hardware.scope import MalariaScope
from ulc_mm_package.scope_constants import ACQUISITION_PERIOD


class Acquisition(QObject):
    update_liveview = pyqtSignal(np.ndarray)
    update_infopanel = pyqtSignal()
    update_scopeop = pyqtSignal(np.ndarray, float)

    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(__name__)

        self.img = None
        self.img_timestamp = None
        self.mscope = None

        self.period = ACQUISITION_PERIOD

    @pyqtSlot()
    def create_timers(self):
        self.acquisition_timer = QTimer()
        self.acquisition_timer.setTimerType(Qt.PreciseTimer)
        self.acquisition_timer.timeout.connect(self.get_img)

        self.liveview_timer = QTimer()
        self.liveview_timer.setTimerType(Qt.PreciseTimer)
        self.liveview_timer.timeout.connect(self.send_img)

        self.logger.info("Created acquisition and liveview timers.")

    @pyqtSlot()
    def start_timers(self):
        self.acquisition_timer.start(ACQUISITION_PERIOD)
        self.liveview_timer.start(self.period)

        self.logger.info(
            f"Started acquisition timer with {ACQUISITION_PERIOD} ms period and liveview timer with {self.period} ms period."
        )

    @pyqtSlot()
    def stop_timers(self):
        self.acquisition_timer.stop()
        self.liveview_timer.stop()

        self.logger.info("Stopped acquisition and liveview timers.")

    @pyqtSlot(bool)
    def freeze_liveview(self, freeze):
        if freeze:
            self.liveview_timer.stop()
            self.logger.info("Stopped liveview timer.")
        else:
            self.liveview_timer.start(self.period)
            self.logger.info(f"Started liveview timer with {self.period} ms period.")

    @pyqtSlot(float)
    def set_period(self, period):
        self.period = period
        self.liveview_timer.setInterval(self.period)

    @pyqtSlot(MalariaScope)
    def get_mscope(self, mscope: MalariaScope):
        self.mscope = mscope

    def get_img(self):
        img_gen = self.mscope.camera.yieldImages()
        try:
            self.img, self.img_timestamp = next(img_gen)
            self.update_scopeop.emit(self.img, self.img_timestamp)
        except PyCamerasError as e:
            self.logger.exception(e)

    def send_img(self):
        self.update_liveview.emit(self.img)
        self.update_infopanel.emit()
