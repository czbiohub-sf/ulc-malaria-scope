""" daA1600-60um - Basler dart camera

See camera module under hardware/real/ for more info.

"""

from ulc_mm_package.hardware.hardware_wrapper import hardware
from ulc_mm_package.hardware.hardware_constants import DEVICELINK_THROUGHPUT


class CameraError(Exception):
    """Base class for catching camera errors."""
    # Note this is temporary until the pyCameras improved exception-handling PR is merged.
    # Once that is merged, we can simply raise the PyCameras error.

@hardware
class BaslerCamera:
    """Extends the Basler camera class from pycameras and makes a few ULCMM specific configuration changes."""

@hardware
class AVTCamera:
    pass