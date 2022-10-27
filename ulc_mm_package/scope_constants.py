import os
import usb

from typing import Tuple
from enum import auto, Enum
from collections import namedtuple


class MissingCameraError(Exception):
    ...


ImageDims = namedtuple("ImageDims", ["width", "height"])


class CameraOptions(Enum):
    AVT = auto()
    BALSER = auto()
    SIMULATED = auto()

    def img_dims(self) -> ImageDims:
        if self == CameraOptions.AVT:
            return ImageDims(width=600, height=800)
        elif self == CameraOptions.BASLER:
            return ImageDims(width=772, height=1032)
        elif self == CameraOptions.SIMULATED:
            return ImageDims(width=600, height=800)

    @property
    def IMG_WIDTH(self) -> int:
        return self.img_dims().width

    @property
    def IMG_HEIGHT(self) -> int:
        returnself.img_dims().height


MS_SIMULATE_FLAG = int(os.environ.get("MS_SIMULATE", 0))
SIMULATION = MS_SIMULATE_FLAG > 0

AVT_VENDOR_ID = 0x1AB2
AVT_PRODUCT_ID = 0x0001

BASLER_VENDOR_ID = 0x2676
BASLER_PRODUCT_ID = 0xBA03

_avt_dev = usb.core.find(idVendor=AVT_VENDOR_ID, idProduct=AVT_PRODUCT_ID)
_basler_dev = usb.core.find(idVendor=BASLER_VENDOR_ID, idProduct=BASLER_PRODUCT_ID)

if SIMULATION:
    CAMERA_SELECTION = CameraOptions.SIMULATED
elif _avt_dev is not None:
    CAMERA_SELECTION = CameraOptions.AVT
elif _basler_dev is not None:
    CAMERA_SELECTION = CameraOptions.BASLER
else:
    raise MissingCameraError("There is no camera found on the device and we are not simulating: ")
