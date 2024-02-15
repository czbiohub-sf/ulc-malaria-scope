import os
import usb
import socket

from pathlib import Path
from enum import auto, Enum
from collections import namedtuple

curr_dir = Path(__file__).parent.resolve()  # Get full path

# RESEARCH USE ONLY DISCLAIMER
RESEARCH_USE_ONLY = "For Research Use Only. Not for use in diagnostic procedures.\nClick OK to acknowledge that this device is for RESEARCH USE ONLY."

# ================ Simulation constants ================ #
MS_SIMULATE_FLAG = int(os.environ.get("MS_SIMULATE", 0))
SIMULATION = MS_SIMULATE_FLAG > 0

VERBOSE = int(os.environ.get("MS_VERBOSE", 0))

print(f"Simulation mode: {SIMULATION}")

VIDEO_REC = "https://drive.google.com/drive/folders/1YL8i5VXeppfIsPQrcgGYKGQF7chupr56"
VIDEO_PATH = None

if SIMULATION:
    _viable_videos = (
        curr_dir / "QtGUI/sim_media/avt-sample.mp4",
        curr_dir / "QtGUI/sim_media/sample.avi",
        curr_dir / "QtGUI/sim_media/sample.mp4",
    )
    VIDEO_PATH = next((vid for vid in _viable_videos if os.path.exists(vid)), None)
    if VIDEO_PATH is None:
        raise RuntimeError(
            "Sample video for simulation mode could not be found. "
            f"Download a video from {VIDEO_REC} and save as {[str(v) for v in _viable_videos]}"
        )


CONFIGURATION_FILE = curr_dir / "configs" / f"{socket.gethostname()}-config.ini"

# ================ For flowcontrol and classc image focus ================ #
DOWNSAMPLE_FACTOR = 10

# ================ Summary PDF constants ================ #
DEBUG_REPORT = int(
    os.environ.get("DEBUG_REPORT", 0)
)  # Flag to add optional plots (metadata / YOGO histograms) to the summary report
CSS_FILE_NAME = "minimal-table.css"
SUMMARY_REPORT_CSS_FILE = curr_dir / "summary_report" / CSS_FILE_NAME
DESKTOP_SUMMARY_DIR = Path.home() / "Desktop/Remoscope_Summary_Reports"
DESKTOP_CELL_COUNT_DIR = Path.home() / "Desktop/Remoscope_Cell_Counts"

# Create the folders if they don't exist already
for x in [DESKTOP_SUMMARY_DIR, DESKTOP_CELL_COUNT_DIR]:
    Path(x).mkdir(exist_ok=True)

RBCS_PER_UL = 5e6
MAX_THUMBNAILS_SAVED_PER_CLASS = 80


class MissingCameraError(Exception):
    ...


ImageDims = namedtuple("ImageDims", ["width", "height"])


class CameraOptions(Enum):
    AVT = auto()
    BASLER = auto()
    SIMULATED = auto()
    NONE = auto()

    def img_dims(self) -> ImageDims:
        if self == CameraOptions.AVT:
            return ImageDims(height=772, width=1032)
        elif self == CameraOptions.BASLER:
            return ImageDims(height=600, width=800)
        elif self == CameraOptions.SIMULATED:
            # FIXME: if 'avt' in videopath, assume it is an avt vid
            # a bit hacky, but workable for just sim mode
            assert VIDEO_PATH is not None
            if "avt" in str(VIDEO_PATH):
                return ImageDims(height=772, width=1032)
            return ImageDims(height=600, width=800)
        elif self == CameraOptions.NONE:
            # Make these 1 just to be finite
            return ImageDims(height=1, width=1)
        else:
            raise ValueError(
                f"CameraOptions should be one of the following CameraOptions: {[e.value for e in CameraOptions]}"
            )

    @property
    def IMG_WIDTH(self) -> int:
        return self.img_dims().width

    @property
    def IMG_HEIGHT(self) -> int:
        return self.img_dims().height


# ================ Scope lock constants ================ #
LOCKFILE = "lock.py"

# ================ FPS constants ================ #
ACQUISITION_FPS = 30.0
LIVEVIEW_FPS = 1.0

ACQUISITION_PERIOD = 1000.0 / ACQUISITION_FPS  # ms
LIVEVIEW_PERIOD = 1000.0 / LIVEVIEW_FPS  # ms

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
            CAMERA_SELECTION = CameraOptions.NONE

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
    "git_branch",
    "git_commit",
    "autofocus_model",
    "yogo_model",
]

PER_IMAGE_METADATA_KEYS = [
    "im_counter",
    "timestamp",
    "motor_pos",
    "pressure_hpa",
    "pressure_status_flag",
    "led_pwm_val",
    "syringe_pos",
    "flowrate",
    "focus_error",
    "filtered_focus_error",
    "focus_adjustment",
    "classic_sharpness_ratio",
    "cell_count_cumulative",
    "temperature",
    "camera_temperature",
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
    "yogo_qsize",
    "ssaf_qsize",
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
