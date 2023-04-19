""" daA1600-60um - Basler dart camera

See camera module under hardware/real/ for more info.

"""

from abc import ABC, abstractmethod

from ulc_mm_package.hardware.hardware_wrapper import hardware


class CameraError(Exception):
    """Base class for catching camera errors."""

    # Note this is temporary until the pyCameras improved exception-handling PR is merged.
    # Once that is merged, we can simply raise the PyCameras error.


class CameraBase(ABC):
    @abstractmethod
    def yieldImages(self):
        pass


@hardware
class BaslerCamera(CameraBase):
    """Extends the Basler camera class from pycameras and makes a few ULCMM specific configuration changes."""


@hardware
class AVTCamera(CameraBase):
    pass
