""" daA1600-60um - Basler dart camera

-- Important Links --
Basler API:
    https://docs.baslerweb.com/area-scan-cameras
        Make sure to select the camera model in the top-right
        Click on "Features" in the menu on the left to view the API functions
Basler PyPlon Library:
    https://github.com/basler/pypylon
"""

import sys

from py_cameras import Basler, GrabStrategy
from ulc_mm_package.hardware.hardware_constants import DEFAULT_EXPOSURE_MS
from ulc_mm_package.hardware.hardware_errors import CameraError

# ------ CONSTANTS ------ #
_DEFAULT_EXPOSURE_MS = 0.25

class CameraError(Exception):
    """Base class for catching camera errors."""

    # Note this is temporary until the pyCameras improved exception-handling PR is merged.
    # Once that is merged, we can simply raise the PyCameras error.

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