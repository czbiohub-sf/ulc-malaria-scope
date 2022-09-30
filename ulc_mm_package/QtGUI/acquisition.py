import traceback
import numpy as np

from time import perf_counter, sleep
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot


class Acquisition(QObject):
    update_liveview = pyqtSignal(np.ndarray)
    update_scopeop = pyqtSignal(np.ndarray)

    def __init__(self):
        super().__init__()

        self.mscope = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.get_img)

        self.running = True
        self.count = 0
        
        self.a = 0
        self.b = 0

    def get_mscope(self, mscope):
        self.mscope = mscope

    def get_img(self):
        try: 
            self.a = perf_counter()
            # print("GET IMG {}".format(self.a-self.b))
            self.b = self.a    

            img = next(self.mscope.camera.yieldImages())
            self.update_liveview.emit(img)
            self.update_scopeop.emit(img)
            self.count += 1
        except Exception as e:
            # This catch-all is here temporarily until the PyCameras error-handling PR is merged (https://github.com/czbiohub/pyCameras/pull/5)
            # Once that happens, this can be swapped to catch the PyCameraException
            print(e)
            print(traceback.format_exc())