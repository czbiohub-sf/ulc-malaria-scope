import traceback
import numpy as np

from time import perf_counter, sleep
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from ulc_mm_package.QtGUI.gui_constants import (
    ACQUISITION_PERIOD,
    LIVEVIEW_PERIOD,
)
    

class Acquisition(QObject):
    update_liveview = pyqtSignal(np.ndarray)
    update_scopeop = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        # self.img = None
        self.img = None
        self.mscope = None

        self.acquisition_timer = QTimer()
        self.acquisition_timer.timeout.connect(self.get_img)
        
        self.liveview_timer = QTimer()
        self.liveview_timer.timeout.connect(self.send_img)

        self.running = True
        self.count = 0
        
        self.a = 0
        self.b = 0
        
    def start(self):
        self.acquisition_timer.start(ACQUISITION_PERIOD)
        self.liveview_timer.start(ACQUISITION_PERIOD)
        
    # def stop(self):
    #     self.acquisition_timer.stop()
    #     self.liveview_timer.stop()
        
    @pyqtSlot(float)
    def set_fps(self, period):
        self.liveview_timer.setInterval(period)

    def get_mscope(self, mscope):
        self.mscope = mscope
        # self.img = next(self.mscope.camera.yieldImages())
        
    def send_img(self):
        self.update_liveview.emit(self.img)

    def get_img(self):
        self.a = perf_counter()
        # print("GET IMG {}".format(self.a-self.b))
        self.b = self.a    
        try:

            self.img = next(self.mscope.camera.yieldImages())
            # print(img-self.img)
            
            # self.img = img
            # self.update_liveview.emit(img)
            self.update_scopeop.emit(self.img)
            self.count += 1
        except Exception as e:
            # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
            # Once that happens, this can be swapped to catch the PyCameraException
            print(e)
            print(traceback.format_exc())
