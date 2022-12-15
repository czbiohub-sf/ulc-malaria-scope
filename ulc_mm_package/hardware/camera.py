""" daA1600-60um - Basler dart camera

See camera module under hardware/real/ for more info.

"""

from ulc_mm_package.hardware.hardware_wrapper import hardware


ImageDims = namedtuple("ImageDims", ["width", "height"])


class CameraDims:
    w = None
    h = None

    @classmethod
    def _set_height(h: int):
        h = h

    @classmethod
    def _set_width(w: int):
        w = w

    def set_resolution(w: int, h: int):
        CameraDims._set_width(w)
        CameraDims._set_height(h)

    @classmethod
    def get_dims() -> ImageDims:
        if CameraDims.h == None or CameraDims.w == None:
            raise ValueError(
                f"Resolution has not been set - the camera module should set this on instantiation by calling CameraDims.set_resolution(height, width) or if it ever changes its binning mode."
            )

        return ImageDims(CameraDims.w, CameraDims.h)

    @property
    def IMG_HEIGHT():
        return CameraDims.get_dims().height

    @property
    def IMG_WIDTH(self):
        return CameraDims.get_dims().width


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
