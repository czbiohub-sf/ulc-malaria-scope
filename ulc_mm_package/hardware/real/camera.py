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
import logging
from enum import Enum
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


class BinningMode(Enum):
    AVERAGE = "Average"
    SUM = "Sum"


class BaslerCamera(Basler):
    """Extends the Basler camera class from pycameras and makes a few ULCMM specific configuration changes."""

    def __init__(self):
        try:
            super().__init__()

            self.logger = logging.getLogger(__name__)

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
    """A class initially written for the AVT Alvium 1800 U-319m mono bareboard which wraps
    AVT's `VimbaPython' library (https://github.com/alliedvision/VimbaPython)

    A couple things to be aware of about this wrapper:
    - This wrapper circumvents AVT's recommended context-manager usage structure, i.e instead of:
    (pseudocode):

        with cam:
            cam.start_streaming()
            ...

    We instantiate an AVT Camera object:

        cam = AVTCamera()

    The reason for this was the initial malaria scope software was written for a Basler Camera.
    There was a brief period of time during development when we had two scopes using the Basler, and one using the AVT.
    To make the software run on either camera with minimal changes, this wrapper was created so that the AVT
    would be a drop-in replacement for the Basler.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Internal variables used to keep track of the number of
        # > total images
        # > incomplete frames
        # > frames dropped (i.e the caller attempted to get an image but none were in the queue),
        # > times a frame was attempted to be placed in the queue but failed because the queue was full
        self.all_count = 0
        self.incomplete_count = 0
        self.dropped_count = 0
        self.full_count = 0

        self._isActivated = False
        self.vimba = Vimba.get_instance().__enter__()
        self.queue: queue.Queue[Tuple[np.ndarray, float]] = queue.Queue(maxsize=1)
        self.connect()

    def __del__(self):
        """Cleanup - however best not to rely on __del__."""
        self.deactivateCamera()

    def _get_camera(self):
        """Returns the first listed AVT camera."""
        with Vimba.get_instance() as vimba:
            cams = vimba.get_all_cameras()
            return cams[0]

    def _camera_setup(self):
        """Default settings for use with the malaria scope."""
        self.minExposure_ms, self.maxExposure_ms = self.getExposureBoundsMilliseconds()
        self.setDeviceLinkThroughputLimit(DEVICELINK_THROUGHPUT)
        self.camera.ExposureAuto.set("Off")
        self.exposureTime_ms = DEFAULT_EXPOSURE_MS

        # Flip image in y (malaria scope specific nuance, want RBCs to be flowing 'downward' in the display)
        self.camera.ReverseY.set(True)

        # 2x2 binning
        self.setBinning(bin_factor=2)

        # Monochrome uint8
        self.camera.set_pixel_format(vimba.PixelFormat.Mono8)

    def connect(self) -> None:
        """Get and connect to the camera using an explicit __enter__ (circumvent the context manager)
        and set default camera settings.
        """

        self.camera = self._get_camera()
        self.camera.__enter__()
        self._camera_setup()
        self._isActivated = True

    def deactivateCamera(self) -> None:
        """Deactivate the camera, manually exit the context manager using __exit__"""
        self.logger.info(
            f"CAMERA status: all={self.all_count} | full={self.full_count} | "
            f"incomplete={self.incomplete_count} | dropped={self.dropped_count}"
        )
        self.stopAcquisition()
        self.vimba.__exit__(*sys.exc_info())

    def _frame_handler(self, cam, frame):
        """A callback used by Vimba under the hood, this function is called
        every time a new frame is ready and runs asynchronously.

        The frame handler will attempt to remove the most recent image in the queue.
        If the queue is empty, it'll ignore the exception that is raised.

        Then it will place the current image into the queue (as a tuple of image and current timestamp).
        """

        try:
            self.queue.get_nowait()
        except queue.Empty:
            pass

        self.all_count += 1
        if frame.get_status() == vimba.FrameStatus.Complete:
            try:
                self.queue.put_nowait(
                    (frame.as_numpy_ndarray()[:, :, 0].copy(), perf_counter())
                )
            except queue.Full:
                self.full_count += 1
                self.logger.warning(
                    f"queue full in _frame_handler. full_count={self.full_count}"
                )
            except np.core._exceptions.MemoryError as e:
                self.logger.error(
                    "memory error when trying to copy image into numpy array in _frame_handler"
                )
                raise e
        else:
            self.incomplete_count += 1
            self.logger.warning(
                f"camera returned incomplete frame. incomplete_count={self.incomplete_count}"
            )

        cam.queue_frame(frame)

    def _flush_queue(self):
        """Clear the queue of images."""

        with self.queue.mutex:
            self.queue.queue.clear()

    def startAcquisition(self) -> None:
        """Begin acquisition, set the camera's callback function (i.e the function that is called everytime a new frame is ready)."""

        if not self.camera.is_streaming():
            self.camera.start_streaming(self._frame_handler)

    def stopAcquisition(self) -> None:
        """Stop streaming."""

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
                self.dropped_count += 1
                self.logger.warning("Dropped frame.")

    def setBinning(self, mode: BinningMode = BinningMode.AVERAGE, bin_factor=1):
        """Set the binning mode.

        Parameters
        ----------
        mode: BinningMode (enum)
            Either BinningMode.AVERAGE or BinningMode.SUM

        bin_factor: int
        """
        while self.camera.is_streaming():
            self.camera.stop_streaming()

        self.camera.BinningHorizontalMode.set(mode.value)
        self.camera.BinningVerticalMode.set(mode.value)
        self.camera.BinningHorizontal.set(bin_factor)
        self.camera.BinningVertical.set(bin_factor)

        # For some reason, setting the binning mode only changes the maximum image width/height, and not the current
        # image width/height. So they must be set manually. (I figured this out by looking at the Vimba Viewer and noticing
        # that the max height/width were changed when adjusting binning factor, but not the current image height/width)
        self.camera.Width.set(self.camera.WidthMax.get())
        self.camera.Height.set(self.camera.HeightMax.get())

    def getBinning(self):
        """Return the binning factor."""
        return self.camera.BinningHorizontal.get()

    def setDeviceLinkThroughputLimit(self, bytes_per_second: int):
        """Set the device link throughput (in bytes)."""
        self.camera.DeviceLinkThroughputLimit.set(bytes_per_second)

    def _getTemperature(self) -> float:
        """Get the device temperature."""
        try:
            return self.camera.DeviceTemperature.get()
        except Exception as e:
            self.logger.error(
                "Could not get the device temperature using DeviceTemperature: {e}"
            )
            raise e

    def _setExposureTimeMilliseconds(self, value_ms: int) -> None:
        """Set the exposure time.

        Parameters
        ----------
        value_ms: int
            Desired exposure time in milliseconds.
        """
        try:
            self.camera.ExposureTime.set(value_ms * 1000)
        except Exception as e:
            self.logger.error("Could not set exposure using ExposureTime.set().")
            raise e

    def _getCurrentExposureMilliseconds(self) -> float:
        """Return the current exposure time in milliseconds.

        Returns
        -------
        float: exposure time in milliseconds
        """
        try:
            return self.camera.ExposureTime.get() / 1000
        except Exception as e:
            self.logger.error(
                f"ExposureTime method failed - could not get the current ExposureTime: {e}"
            )
            raise e

    def getExposureBoundsMilliseconds(self) -> Tuple[float, float]:
        """Get the min/max exposure time bounds

        Returns
        -------
        Tuple[float, float]:
            Min and max exposure times in milliseconds
        """

        try:
            minExposure_ms = self.camera.ExposureAutoMin.get() / 1000
            maxExposure_ms = self.camera.ExposureAutoMax.get() / 1000
            return (minExposure_ms, maxExposure_ms)
        except Exception as e:
            self.logger.error(
                f"Could not get exposure using ExposureAutoMin / ExposureAutoMax: {e}"
            )
            raise e

    @property
    def exposureTime_ms(self):
        return self._exposureTime_ms

    @exposureTime_ms.setter
    def exposureTime_ms(self, value_ms: int):
        if self.minExposure_ms < value_ms < self.maxExposure_ms:
            try:
                self._setExposureTimeMilliseconds(value_ms)
                exposureFromCamera = self._getCurrentExposureMilliseconds()
                self._exposureTime_ms = exposureFromCamera
                self.logger.info(f"Exposure time set to {exposureFromCamera} ms.")
            except Exception as e:
                self.logger.warning(f"Failed to set exposure: {e}")
                raise e
        else:
            raise ValueError(
                "value_ms out of range: must be in "
                "[{self.minExposure_ms, self.maxExposure_ms}], but value_ms={value_ms}"
            )
