import os
import usb

from os import listdir
from typing import Tuple
from enum import auto, Enum
from collections import namedtuple


class MissingCameraError(Exception):
    ...


ImageDims = namedtuple("ImageDims", ["width", "height"])


class CameraOptions(Enum):
    AVT = auto()
    BASLER = auto()
    SIMULATED = auto()

    def img_dims(self) -> ImageDims:
        if self == CameraOptions.AVT:
            return ImageDims(height=772, width=1032)
        elif self == CameraOptions.BASLER:
            return ImageDims(height=600, width=800)
        elif self == CameraOptions.SIMULATED:
            return ImageDims(height=600, width=800)

    @property
    def IMG_WIDTH(self) -> int:
        return self.img_dims().width

    @property
    def IMG_HEIGHT(self) -> int:
        return self.img_dims().height


# ================ Data storage metadata ================ #
EXPERIMENT_METADATA_KEYS = [
    "operator_id",
    "participant_id",
    "flowcell_id",
    "target_flowrate",
    "site",
    "notes",
    "scope",
    "camera",
    "exposure",
    "target_brightness",
]

PER_IMAGE_METADATA_KEYS = [
    "im_counter",
    "timestamp",
    "motor_pos",
    "pressure_hpa",
    "syringe_pos",
    "flowrate",
    "focus_error",
    "cell_density",
    "temperature",
    "humidity",
]

# ================ Simulation constants ================ #
MS_SIMULATE_FLAG = int(os.environ.get("MS_SIMULATE", 0))
SIMULATION = MS_SIMULATE_FLAG > 0
print(f"Simulation mode: {SIMULATION}")

# ================ SSD directory constants ================ #
if SIMULATION:
    SSD_DIR = "../QtGUI/sim_media/pi/"
else:
    SSD_DIR = "/media/pi/"

try:
    EXT_DIR = SSD_DIR + listdir(SSD_DIR)[0] + "/"
except FileNotFoundError as e:
    raise FileNotFoundError(
        f"Could not find any folders within {SSD_DIR}, check that SSD is plugged in."
    ) from e
except IndexError as e:
    raise IndexError(
        f"Could not find any folders within {SSD_DIR}, check that SSD is plugged in."
    ) from e

# ================ Camera constants ================ #
AVT_VENDOR_ID = 0x1AB2
AVT_PRODUCT_ID = 0x0001

BASLER_VENDOR_ID = 0x2676
BASLER_PRODUCT_ID = 0xBA03

try:
    _avt_dev = usb.core.find(idVendor=AVT_VENDOR_ID, idProduct=AVT_PRODUCT_ID)
    _basler_dev = usb.core.find(idVendor=BASLER_VENDOR_ID, idProduct=BASLER_PRODUCT_ID)

    if SIMULATION:
        CAMERA_SELECTION = CameraOptions.SIMULATED
    else:
        if _avt_dev is not None:
            CAMERA_SELECTION = CameraOptions.AVT
        elif _basler_dev is not None:
            CAMERA_SELECTION = CameraOptions.BASLER
        else:
            raise MissingCameraError(
                "There is no camera found on the device and we are not simulating: "
            )

except usb.core.NoBackendError:
    CAMERA_SELECTION = CameraOptions.SIMULATED
