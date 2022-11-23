""" Basler dart camera (daA1600-60um) / AVT Camera (AVT Alvium 1800 U-319m mono bareboard)

-- Important Links --
Basler API:
    https://docs.baslerweb.com/area-scan-cameras
         Make sure to select the camera model in the top-right
        Click on "Features" in the menu on the left to view the API functions
Basler PyPlon Library:
    https://github.com/basler/pypylon
"""

import sys
from time import perf_counter
import queue
from typing import Generator, Tuple

import numpy as np
import vimba
from vimba import Vimba

from py_cameras import Basler, GrabStrategy

from ulc_mm_package.hardware.hardware_constants import (
    DEFAULT_EXPOSURE_MS,
    DEVICELINK_THROUGHPUT,
)
from ulc_mm_package.hardware.camera import CameraError


class BaslerCamera(Basler):
    """Extends the Basler camera class from pycameras and makes a few ULCMM specific configuration changes."""

    def __init__(self):
        try:
            super().__init__()

            # 2x2 binning w/ averaging (https://docs.baslerweb.com/binning)
            # Note that setting the binning mode to "Sum" saturates the values (i.e if
            # the pixel mode is 8-bit (0-256), summing does NOT increase the maximum value to 512)
            self.setBinning(bin_factor=2, mode="Average")
            self.camera.PixelFormat.SetValue("Mono8")
            self.exposureTime_ms = DEFAULT_EXPOSURE_MS
            self.grabStrategy = GrabStrategy.LATEST_IMAGE_ONLY
        except Exception:
            raise CameraError("Camera could not be instantiated.")

    def yieldImages(self):
        return super().yieldImages(self.grabStrategy)

    def _getTemperature(self):
        return self.camera.DeviceTemperature.GetValue()


class AVTCamera:
    def __init__(self):
        self._isActivated = False
        self.vimba = Vimba.get_instance().__enter__()
        self.queue = queue.Queue(maxsize=1)
        self.connect()

    def __del__(self):
        self.deactivateCamera()

    def _get_camera(self):
        with Vimba.get_instance() as vimba:
            cams = vimba.get_all_cameras()
            return cams[0]

    def _camera_setup(self):
        self.minExposure_ms, self.maxExposure_ms = self.getExposureBoundsMilliseconds()
        self.setDeviceLinkThroughputLimit(DEVICELINK_THROUGHPUT)
        self.camera.ExposureAuto.set("Off")
        self.exposureTime_ms = DEFAULT_EXPOSURE_MS
        self.camera.ReverseY.set(True)
        self.setBinning(bin_factor=2)
        self.camera.set_pixel_format(vimba.PixelFormat.Mono8)

    def connect(self) -> None:
        self.camera = self._get_camera()
        self.camera.__enter__()
        self._camera_setup()
        self._isActivated = True

    def deactivateCamera(self) -> None:
        self.stopAcquisition()
        self.vimba.__exit__(*sys.exc_info())

    def _frame_handler(self, cam, frame):
        if self.queue.full():
            self.queue.get()
        if frame.get_status() == vimba.FrameStatus.Complete:
            self.queue.put((np.copy(frame.as_numpy_ndarray()[:, :, 0]), perf_counter()))
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

    def yieldImages(self) -> Generator[Tuple[np.ndarray, float], None, None]:
        """Generator of images

        Yields
        ------
        Tuple[np.ndarray, float]:
            Returns an image array and a timestamp (float)

        Exceptions
        ----------
        queue.Empty:
            Raised if no frames are received within 0.5s while the camera is streaming
        """

        if not self.camera.is_streaming():
            self._flush_queue()
            self.startAcquisition()

        while self.camera.is_streaming():
            # Half a second timeout before queue Empty exception is raised
            try:
                yield self.queue.get(timeout=0.5)
            except queue.Empty:
                # TODO change to logging
                print("Dropped frame.")

    def setBinning(self, mode: str = "Average", bin_factor=1):
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

    def setDeviceLinkThroughputLimit(self, bytes_per_second: int):
        self.camera.DeviceLinkThroughputLimit.set(bytes_per_second)

    def _getTemperature(self):
        try:
            return self.camera.DeviceTemperature.get()
        except:
            print("Could not get the device temperature using DeviceTemperature.")
        raise

    def _setExposureTimeMilliseconds(self, value_ms: int):
        try:
            self.camera.ExposureTime.set(value_ms * 1000)
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
            minExposure_ms = self.camera.ExposureAutoMin.get() / 1000
            maxExposure_ms = self.camera.ExposureAutoMax.get() / 1000
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
