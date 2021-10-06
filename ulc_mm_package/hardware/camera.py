import sys
from time import perf_counter
import queue
import threading
import cv2
import numpy as np
from pypylon import pylon

sys.setswitchinterval(0.001)

# ------ CONSTANTS ------ #
_DEFAULT_EXPOSURE_US = 1000
_DEFAULT_GRABRESULT_TIMEOUT_MS = 100

class StoppableThread(threading.Thread):
    """Thread class which can be stopped"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self.daemon = True

    def stop(self):
        self._stop_event.set()

    def isStopped(self):
        return self._stop_event.is_set()

class BaslerCamera:
    def __init__(self):
        try:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        except Exception as e:
            self.instantiated = False
            print(f"Error instantiating camera.\n======Traceback======\n{e}\n============")
            return

        # Open and set camera configuration
        self.camera.Open()
        self.camera.PixelFormat.SetValue("Mono8")

        # 2x2 binning w/ averaging (https://docs.baslerweb.com/binning)
        # Note that setting the binning mode to "Sum" saturates the values (i.e if
        # the pixel mode is 8-bit (0-256), summing does NOT increase the maximum value to 512)
        self.camera.BinningHorizontalMode.SetValue("Average")
        self.camera.BinningVerticalMode.SetValue("Average")
        self.camera.BinningHorizontal.SetValue(2)
        self.camera.BinningVertical.SetValue(2)

        # Turn off auto exposure and gain
        self.camera.ExposureAuto.SetValue('Off')
        self.camera.GainAuto.SetValue('Off')

        self.grab_timeout = _DEFAULT_GRABRESULT_TIMEOUT_MS
        self.camera_model = self.camera.GetDeviceInfo().GetModelName()
        self.min_exposure = self.camera.ExposureTime.GetMin()
        self.max_exposure = self.camera.ExposureTime.GetMax()
        self.setExposure(_DEFAULT_EXPOSURE_US)
        self.instantiated = True

    def close(self):
        self.camera.Close()

    def printProperties(self):
        curr_exposure = self.camera.ExposureTime.GetValue()
        print(f"Camera model: {self.camera_model}")
        print(f"Horizontal binning mode: {self.camera.BinningHorizontalMode.GetValue()}")
        print(f"Vertical binning mode: {self.camera.BinningVerticalMode.GetValue()}")
        print(f"Exposure time: {curr_exposure} us (min: {self.min_exposure} / max: {self.max_exposure})")

    def setExposure(self, exposure_us):
        if not self.min_exposure <= exposure_us <= self.max_exposure:
            raise ValueError(f"Exposure not within allowable range.\nMinimum exposure is: {self.min_exposure} us. Max exposure is {self.max_exposure} us.")
        if exposure_us > self.grab_timeout:
            self.camera.ExposureTime.SetValue(exposure_us)
        else:
            # Ensure the grab timeout is less than the exposure
            self.grab_timeout = int(self.grab_timeout / 2)
            self.setExposure(exposure_us)

    def __del__(self):
        if self.instantiated:
            self.camera.AcquisitionStop.Execute()
            self.camera.Close()

class QueueCamera(BaslerCamera):
    def __init__(self, framerate: int, image_queue: queue.LifoQueue):
        super().__init__()
        self.interval = 1 / framerate
        self.image_queue = image_queue
        self.q_thread = None
        self.camera.AcquisitionMode.SetValue("Continuous")

    def __del__(self):
        if self.instantiated:
            self.stop()
            super().__del__()

    def flushQueue(self):
        while not self.image_queue.empty():
            try:
                self.image_queue.get()
            except queue.Empty:
                continue
            self.image_queue.task_done()
            
    def setFramerate(self, framerate):
        self.interval = 1 / framerate
        self.camera.ExposureTime.SetValue(self.interval*1000000)

    def _streamToQueue(self):
        start_time = perf_counter()
        while True:
            if perf_counter() - start_time >= self.interval:
                # self.camera.TriggerSoftware.Execute()
                grabResult = self.camera.RetrieveResult(100, pylon.TimeoutHandling_ThrowException)
                if grabResult and grabResult.GrabSucceeded():
                    self.image_queue.put(grabResult.Array)
                    start_time = perf_counter()
                grabResult.Release()

    def streamToQueue(self):
        if not self.camera.IsGrabbing():
            self.camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
        self.q_thread = StoppableThread(target=self._streamToQueue).start()

    def stop(self):
        if self.q_thread != None:
            self.q_thread.stop()
            self.q_thread.join()
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()

class LiveCamera(BaslerCamera):
    def __init__(self):
        super().__init__()

    def yieldImages(self) -> np.ndarray:
        """Returns a generator of grayscale images as numpy arrays"""
        # Set up continuous acquisition of the latest image only
        if not self.camera.IsGrabbing():
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        while self.camera.IsGrabbing():
            grabResult = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            if grabResult and grabResult.GrabSucceeded():
                yield grabResult.Array
                grabResult.Release()

    def streamAndViewImages(self):
        for img in self.yieldImages():
            cv2.imshow("Live view with generator", img)
            cv2.waitKey(1)
            if cv2.getWindowProperty("Live view", cv2.WND_PROP_VISIBLE) < 1:
                self.stop()
                break

    def stop(self):
        cv2.destroyAllWindows()
        if self.camera.IsGrabbing():
            self.camera.StopGrabbing()

def queueCameraTest(duration: int, framerate: int):
    q = queue.LifoQueue()
    # framerate = (framerate - 2.554) / 0.7525
    qCam = QueueCamera(framerate, q)
    qCam.printProperties()

    if qCam.instantiated:
        qCam.streamToQueue()
        now = perf_counter()
        while perf_counter() - now < duration:
            pass
        qCam.stop()
        print(f"Set: {framerate} fps, Actual: ({q.qsize()/duration:.2f} fps)")
    qCam.camera.Close()
    del(qCam)
    return q.qsize() / duration

def liveCameraLiveViewTest():
    livecam = LiveCamera()
    livecam.streamAndViewImages()
    livecam.stop()

    del(livecam)

def liveCameraImageGeneratorTest():
    livecam = LiveCamera()
    for img in livecam.yieldImages():
        cv2.imshow("Live camera image generator", img)
        cv2.waitKey(1)
        if cv2.getWindowProperty("Live camera image generator", cv2.WND_PROP_VISIBLE) < 1:
            livecam.stop()
            break

if __name__ == "__main__":
    # desired = []
    # actual = []
    # for framerate in range(55, 61, 10):
    #     desired.append(framerate)
    #     actual.append(queueCameraTest(3, framerate))

    # coeffs = np.polyfit(desired, actual, 1)
    # print(coeffs)
    # plt.plot(desired, actual)
    # plt.show()
    queueCameraTest(3, 60)
    # liveCameraLiveViewTest()
    # liveCameraImageGeneratorTest()

    # # Basic test 
    # camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    # camera.Open()
    # camera.PixelFormat.SetValue("Mono8")
    # camera.BinningHorizontalMode.SetValue("Average")
    # camera.BinningVerticalMode.SetValue("Average")
    # camera.BinningHorizontal.SetValue(2)
    # camera.BinningVertical.SetValue(2)
    # print(camera.ExposureTime.GetValue())
    # print(camera.ExposureTime.GetMax())
    # print(camera.ExposureTime.GetMin())
    # camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    # start = perf_counter()
    # frame_counter = 0
    # while perf_counter() - start < 10:
    #     grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    #     if grabResult and grabResult.GrabSucceeded():
    #         frame_counter += 1
    # print(f"{frame_counter/10}")
    