import sys
import threading

from time import sleep
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QRunnable, QObject, QThreadPool

# from ulc_mm_package.hardware.scope import MalariaScope

QtWidgets.QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

# Qt GUI Files
_UI_FILE_DIR = "dev_run.ui"

class Autopilot(QObject):
    test = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.stop = False

    @pyqtSlot(int)
    def doSomethingWithInt(self, val):
        sleep(1)
        print(f"It's ya boi {val}")

    def sayHi(self):
        print("Suh dude")
        # sleep(10)

class AcquisitionThread(QThread):
    test = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.stop = False
    
    def run(self):
        while not self.stop:
            self.test.emit(1)
            print("working")
            sleep(0.03)

class MalariaScopeGUI(QtWidgets.QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MalariaScopeGUI, self).__init__(*args, **kwargs)

        # Load the ui file
        uic.loadUi(_UI_FILE_DIR, self)
        self.btnExit.clicked.connect(self.exit)

        self.autopilot = Autopilot()
        self.worker_thread = QThread()
        self.autopilot.moveToThread(self.worker_thread)
        self.worker_thread.start()

        self.acquistionThread = AcquisitionThread()
        # self.acquistionThread.test.connect(self.longRunningSlot)
        self.acquistionThread.test.connect(self.autopilot.doSomethingWithInt)
        self.acquistionThread.start()

    @pyqtSlot(int)
    def longRunningSlot(self, val):
        print("In longRunningSlot")
        # sleep(1)
        # self.autopilot.doSomethingWithInt(val)
        self.autopilot.sayHi()

    def exit(self):
        self.acquistionThread.stop = True
        self.acquistionThread.wait()
        quit()

class ExperimentFlow:
    def __init__(self):
        pass

    def state1():
        pass

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_window = MalariaScopeGUI()
    main_window.show()
    sys.exit(app.exec_())

# # class Autopilot(QRunnable):

# #     def __init__(self):
# #         self.stop = False
# #         # self.mscope = mscope
# #         super(Autopilot, self).__init__()

# #         self.sig = WorkerSignals()
# #         # self.setAutoDelete(True)

# #         # self.generator = func

# #     def run(self):

# #         print(threading.active_count())
# #         self.sig.mem_signal.emit(2)
# #         sleep(1)

# #         # while True:
# #         #     if len(self.q) > 0:
# #         #         print("LOOK {}".format(self.q.pop()))

# #         # for val in self.generator:
# #         #     print("Look {val}")

# #         # while True:
# #         #     self.sayHi()
# #         #     sleep(1)

# #     def doSomethingWithInt(self, val):
# #         pass
# #         # print(f"It's ya boi {val}")

# #     def sayHi(self):
# #         print("Suh dude")
# #         # sleep(10)

# class Autopilot(QThread):
#     test = pyqtSignal(int)
#     def __init__(self):
#         super().__init__()
#         self.stop = False

#         def run(self, val):
#             print
    
#     def doSomethingWithInt(self, val):
#         pass
#         # print(f"It's ya boi {val}")

#     def sayHi(self):
#         print("Suh dude")
#         # sleep(10)

# class AcquisitionThread(QThread):
#     test = pyqtSignal(int)
#     def __init__(self):
#         super().__init__()
#         self.stop = False
    
#     def run(self):
#         while not self.stop:
#             self.test.emit(1)
#             print("working")
#             sleep(0.03)

# class WorkerSignals(QObject):
#     mem_signal = pyqtSignal(int)

# class MalariaScopeGUI(QtWidgets.QMainWindow):
#     def __init__(self, *args, **kwargs):
#         super(MalariaScopeGUI, self).__init__(*args, **kwargs)

#         # Load the ui file
#         uic.loadUi(_UI_FILE_DIR, self)
#         self.btnExit.clicked.connect(self.exit)

#         # self.obj = self.func()

#         # self.q = []

#         # Thread
#         self.thread_pool = QThreadPool()

#         self.thread_pool.setMaxThreadCount(3)

#         self.autopilotThread = Autopilot()
#         self.autopilotThread.sig.mem_signal.connect(self.doT)
#         # self.autopilotThread.start()

#         self.acquistionThread = AcquisitionThread()
#         self.acquistionThread.test.connect(self.longRunningSlot)
#         self.acquistionThread.start()

#         self.thread_pool.start(self.autopilotThread)
