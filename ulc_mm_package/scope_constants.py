import os
import usb

from typing import Tuple
from enum import auto, Enum
from collections import namedtuple


# ================ Simulation constants ================ #
MS_SIMULATE_FLAG = int(os.environ.get("MS_SIMULATE", 0))
SIMULATION = MS_SIMULATE_FLAG > 0

VERBOSE = int(os.environ.get("MS_VERBOSE", 0))

print(f"Simulation mode: {SIMULATION}")

VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"
VIDEO_PATH = None

if SIMULATION:
    _viable_videos = (
        "../QtGUI/sim_media/avt-sample.mp4",
        "../QtGUI/sim_media/sample.avi",
        "../QtGUI/sim_media/sample.mp4",
    )
    VIDEO_PATH = next((vid for vid in _viable_videos if os.path.exists(vid)), None)
    if VIDEO_PATH == None:
        raise RuntimeError(
            "Sample video for simulation mode could not be found. "
            f"Download a video from {VIDEO_REC} and save as {_viable_videos[0]} or {_viable_videos[1]}"
        )


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
            # FIXME: if 'avt' in videopath, assume it is an avt vid
            # a bit hacky, but workable for just sim mode
            assert VIDEO_PATH is not None
            if "avt" in VIDEO_PATH:
                return ImageDims(height=772, width=1032)
            return ImageDims(height=600, width=800)
        raise ValueError("this is impossible because this class is an enum")

        raise ValueError(
            f"CameraOptions somehow gained an enum type {self}. "
            "Please report this strange bug!"
        )

    @property
    def IMG_WIDTH(self) -> int:
        return self.img_dims().width

    @property
    def IMG_HEIGHT(self) -> int:
        return self.img_dims().height


# ================ Camera constants ================ #
MAX_FRAMES = 20000  # Rounded up from 10 minutes of data at 30 FPS
if SIMULATION:
    MAX_FRAMES = 2000

AVT_VENDOR_ID = 0x1AB2
AVT_PRODUCT_ID = 0x0001

BASLER_VENDOR_ID = 0x2676
BASLER_PRODUCT_ID = 0xBA03

try:
    if SIMULATION:
        CAMERA_SELECTION = CameraOptions.SIMULATED
    else:
        _avt_dev = usb.core.find(idVendor=AVT_VENDOR_ID, idProduct=AVT_PRODUCT_ID)
        _basler_dev = usb.core.find(
            idVendor=BASLER_VENDOR_ID, idProduct=BASLER_PRODUCT_ID
        )

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
    "pressure_status_flag",
    "syringe_pos",
    "flowrate",
    "focus_error",
    "temperature",
    "humidity",
    "looptime",
    "runtime",
    "zarrwriter_qsize",
]

PER_IMAGE_TIMING_KEYS = [
    "update_img_count",
    "count_parasitemia",
    "yogo_result_mgmt",
    "pssaf",
    "flowrate_dt",
    "ui_flowrate_focus",
    "img_metadata",
    "datastorage.writeData",
]

if VERBOSE:
    PER_IMAGE_METADATA_KEYS.extend(PER_IMAGE_TIMING_KEYS)

# ================ Environment variables ================ #
NGROK_AUTH_TOKEN_ENV_VAR = "NGROK_AUTH_TOKEN"
EMAIL_PW_TOKEN = "GMAIL_TOKEN"

# ================ SSD directory constants ================ #
SSD_NAME = "SamsungSSD"
if SIMULATION:
    SSD_DIR = "../QtGUI/sim_media/pi/"
else:
    SSD_DIR = "/media/pi/"
