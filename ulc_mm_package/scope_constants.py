import usb

from typing import Tuple
from enum import auto, Enum
from collections import namedtuple


AVT_VENDOR_ID  = 0x1ab2
AVT_PRODUCT_ID = 0x0001

BASLER_VENDOR_ID  = 0x2676
BASLER_PRODUCT_ID = 0xba03


class MissingCameraError(Exception):
    ...


ImageDims = namedtuple("ImageDims", ["width", "height"])


class CameraOptions(Enum):
    AVT = auto()
    BALSER = auto()

    def img_size(self) -> ImageDims:
        if self == CameraOptions.AVT:
            return ImageDims(width=600, height=800)
        elif self == CameraOptions.BASLER:
            return ImageDims(width=772, height=1032)


_avt_dev = usb.core.find(idVendor=AVT_VENDOR_ID, idProduct=AVT_PRODUCT_ID)
_basler_dev = usb.core.find(idVendor=BASLER_VENDOR_ID, idProduct=BASLER_PRODUCT_ID)

# Implicitly, if there is an avt AND a basler connected, pick avt.
# Though, I don't think this is even possible!
if _avt_dev is not None:
    CAMERA_SELECTION = CameraOptions.AVT
elif _basler_dev is not None:
    CAMERA_SELECTION = CameraOptions.BASLER
else:
    raise MissingCameraError("There is no camera found on the device")

