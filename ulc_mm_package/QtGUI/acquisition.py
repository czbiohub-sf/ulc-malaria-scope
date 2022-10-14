""" Image manager

Receives images from the camera and sends them to Liveview and ScopeOp.

"""

import traceback
import numpy as np

from time import perf_counter, sleep
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from ulc_mm_package.QtGUI.gui_constants import ACQUISITION_PERIOD
    

class Acquisition(QObject):
    update_liveview = pyqtSignal(np.ndarray)
    update_scopeop = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        self.img = None
        self.mscope = None

        self.count = 0
        self.period = ACQUISITION_PERIOD
        
        # # For timing
        # self.a = 0
        # self.b = 0

    @pyqtSlot()
    def create_timers(self):
        self.acquisition_timer = QTimer()
        self.acquisition_timer.timeout.connect(self.get_img)
        
        self.liveview_timer = QTimer()
        self.liveview_timer.timeout.connect(self.send_img)

        print("Created timers")

    @pyqtSlot()
    def start_timers(self):
        self.acquisition_timer.start(ACQUISITION_PERIOD)
        self.liveview_timer.start(self.period)

        print("Started timers")
        
    @pyqtSlot()
    def stop_timers(self):
        self.acquisition_timer.stop()
        self.liveview_timer.stop()

    @pyqtSlot(bool)
    def freeze_liveview(self, freeze):
        if freeze: 
            self.liveview_timer.stop()
        else:
            self.liveview_timer.start(self.period)

    @pyqtSlot(float)
    def set_period(self, period):
        self.period = period
        self.liveview_timer.setInterval(self.period)

    def get_mscope(self, mscope):
        self.mscope = mscope

    def get_img(self):
        
        # # For timing
        # self.a = perf_counter()
        # print(f"Acquisition {self.a-self.b}")
        # self.b = self.a
        
        try:
            self.img = next(self.mscope.camera.yieldImages())
            print("sent")
            self.update_scopeop.emit(self.img)
            self.count += 1
        except Exception as e:
            # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
            # Once that happens, this can be swapped to catch the PyCameraException
            print(e)
            print(traceback.format_exc())
        
    def send_img(self):
        self.update_liveview.emit(self.img)