""" daA1600-60um - Basler dart camera

-- Important Links -- 
Basler API:
    https://docs.baslerweb.com/area-scan-cameras 
        Make sure to select the camera model in the top-right
        Click on "Features" in the menu on the left to view the API functions
Basler PyPlon Library:
    https://github.com/basler/pypylon
"""

import threading
from py_cameras import Basler, GrabStrategy

# ------ CONSTANTS ------ #
_DEFAULT_EXPOSURE_MS = 1

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

class ULCMM_Camera(Basler):
    """Extends the Basler camera class from pycameras and makes a few ULCMM specific configuration changes."""

    def __init__(self):
        super().__init__()
    
        # 2x2 binning w/ averaging (https://docs.baslerweb.com/binning)
        # Note that setting the binning mode to "Sum" saturates the values (i.e if
        # the pixel mode is 8-bit (0-256), summing does NOT increase the maximum value to 512)
        self.setBinning(bin_factor=2, mode="Average")
        self.camera.PixelFormat.SetValue("Mono8")
        self.exposureTime_ms = _DEFAULT_EXPOSURE_MS
        self.grabStrategy = GrabStrategy.LATEST_IMAGE_ONLY

    def yieldImages(self):
        return super().yieldImages(self.grabStrategy)