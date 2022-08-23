""" daA1600-60um - Basler dart camera

-- Important Links --
Basler API:
    https://docs.baslerweb.com/area-scan-cameras
         Make sure to select the camera model in the top-right
        Click on "Features" in the menu on the left to view the API functions
Basler PyPlon Library:
    https://github.com/basler/pypylon
"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


class CameraError(Exception):
    """Base class for catching camera errors."""
    # Note this is temporary until the pyCameras improved exception-handling PR is merged.
    # Once that is merged, we can simply raise the PyCameras error.

@hardware
class BaslerCamera:
    pass

class AVTCamera:
    def __init__(self):
        self.vimba = Vimba.get_instance().__enter__()
        self.queue = queue.Queue()
        self.connect()
        self.minExposure_ms, self.maxExposure_ms = self.getExposureBoundsMilliseconds()

    def _get_camera(self):
        with Vimba.get_instance() as vimba:
            cams = vimba.get_all_cameras()
            return cams[0]

    def _camera_setup(self):
        self.camera.ExposureAuto.set("Off")
        self.camera.ExposureTime.set(500)
        self.setBinning(bin_factor=2)
        self.camera.set_pixel_format(vimba.PixelFormat.Mono8)

    def connect(self) -> None:
        self.camera = self._get_camera()
        self.camera.__enter__()
        self._camera_setup()

    def deactivateCamera(self) -> None:
        self.vimba.__exit__(*sys.exc_info())
    
    def _frame_handler(self, cam, frame):
        if self.queue.full():
            self.queue.get_nowait()
        if frame.get_status() == vimba.FrameStatus.Complete:
            self.queue.put(frame.as_numpy_ndarray())
        cam.queue_frame(frame)
    
    def _flush_queue(self):
        with self.queue.mutex:
            self.queue.queue.clear()

    def startAcquisition(self) -> None:
        if not self.camera.is_streaming():
            self.camera.start_streaming(self._frame_handler)

    def stopAcquisition(self) -> None:
        if self.camera.is_streaming():
            self.camera.stop_streaming()

    def yieldImages(self):
        if not self.camera.is_streaming():
            self._flush_queue()
            self.startAcquisition()

        while self.camera.is_streaming():
            yield self.queue.get()[:, :, 0]

    def setBinning(self, mode: str="Average", bin_factor=1):
        while self.camera.is_streaming():
            self.camera.stop_streaming()
        
        self.camera.BinningHorizontalMode.set(mode)
        self.camera.BinningVerticalMode.set(mode)
        self.camera.BinningHorizontal.set(bin_factor)
        self.camera.BinningVertical.set(bin_factor)

        # For some reason, setting the binning mode only changes the maximum image width/height, and not the current
        # image width/height. So they must be set manually. (I figured this out by looking at the Vimba Viewer and noticing
        # that the max height/width were changed when adjusting binning factor, but not the current image height/width)
        self.camera.Width.set(self.camera.WidthMax.get())
        self.camera.Height.set(self.camera.HeightMax.get())

    def getBinning(self):
        return self.camera.BinningHorizontal.get()
    
    def _getTemperature(self):
        try:
            return self.camera.DeviceTemperature.get()
        except:
            print("Could not get the device temperature using DeviceTemperature.")
        raise

    def _setExposureTimeMilliseconds(self, value_ms: int):
        try:
            self.camera.ExposureTime.set(value_ms*1000)
            return
        except:
            print(f"Could not use ExposureTime.set().")

        print(f"Could not set exposure time.")
        raise

    def _getCurrentExposureMilliseconds(self):
        try:
            exposureTime_ms = self.camera.ExposureTime.get() / 1000
            return exposureTime_ms
        except:
            print(f"ExposureTime method failed.")
        print(f"Could not get the current ExposureTime.")
        return None

    def getExposureBoundsMilliseconds(self):
        try:
            minExposure_ms = self.camera.ExposureAutoMin.get()/1000
            maxExposure_ms = self.camera.ExposureAutoMax.get()/1000
            return [minExposure_ms, maxExposure_ms]
        except Exception as e:
            print(e)
            print(f"Could not get exposure using ExposureAutoMin / ExposureAutoMax.")

    @property
    def exposureTime_ms(self):
        return self._exposureTime_ms

    @exposureTime_ms.setter
    def exposureTime_ms(self, value_ms: int):
        if (value_ms > self.minExposure_ms) and (value_ms < self.maxExposure_ms):
            try:
                self._setExposureTimeMilliseconds(value_ms)
                exposureFromCamera = self._getCurrentExposureMilliseconds()
                self._exposureTime_ms = exposureFromCamera
                print(f"Exposure time set to {exposureFromCamera} ms.")

            except:
                print(f"Failed to set exposure'")
        else:
            raise ValueError