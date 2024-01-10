import pathlib
from typing import Tuple, Dict, List

from ulc_mm_package.scope_constants import ACQUISITION_FPS

curr_dir = pathlib.Path(__file__).parent.resolve()  # Get full path


# ================ Autofocus constants ================ #
AF_PERIOD_S = 0.5
AF_PERIOD_NUM = int(
    AF_PERIOD_S * ACQUISITION_FPS
)  # Used for periodic (ie. EWMA) autofocus
AF_BATCH_SIZE = 10  # Used for single shot autofocus

AF_THRESHOLD = 2
AF_QSIZE = 10  # For AF_PERIOD_S = 0.5, we have a max delay of 5 sec

AUTOFOCUS_MODEL_DIR = str(
    curr_dir / "autofocus_model_files" / "polished-dragon-468.xml"
)

# ================ YOGO constants ================ #
YOGO_PRED_THRESHOLD = 0.5
YOGO_CONF_THRESHOLD = 0.9
YOGO_MODEL_DIR = str(
    curr_dir / "yogo_model_files" / "fine-voice-1816" / "fine-voice-1816-quarter.xml"
)
YOGO_CMATRIX_MEAN_DIR = str(
    curr_dir / "yogo_model_files" / "fine-voice-1816" / "frightful-wendigo-1931-cmatrix-mean.npy"
)
YOGO_INV_CMATRIX_STD_DIR = str(
    curr_dir / "yogo_model_files" / "fine-voice-1816" / "frightful-wendigo-1931-inverse-cmatrix-std.npy"
)

YOGO_CLASS_LIST: Tuple[str, ...] = (
    "healthy",
    "ring",
    "trophozoite",
    "schizont",
    "gametocyte",
    "wbc",
    "misc",
)
YOGO_CLASS_IDX_MAP: Dict[str, int] = {k: idx for idx, k in enumerate(YOGO_CLASS_LIST)}
RBC_CLASS_IDS: List[int] = [
    YOGO_CLASS_IDX_MAP["healthy"],
    YOGO_CLASS_IDX_MAP["ring"],
    YOGO_CLASS_IDX_MAP["trophozoite"],
    YOGO_CLASS_IDX_MAP["schizont"],
]
ASEXUAL_PARASITE_CLASS_IDS: List[int] = [
    YOGO_CLASS_IDX_MAP["ring"],
    YOGO_CLASS_IDX_MAP["trophozoite"],
    YOGO_CLASS_IDX_MAP["schizont"],
]
PARASITE_CLASS_IDS: List[int] = [
    YOGO_CLASS_IDX_MAP["ring"],
    YOGO_CLASS_IDX_MAP["trophozoite"],
    YOGO_CLASS_IDX_MAP["schizont"],
    YOGO_CLASS_IDX_MAP["gametocyte"],
]

# best way to find this number is to look for input shape in the model definition xml file
YOGO_CROP_HEIGHT_PX: int = 193

# ================ Image size constants ================ #
IMG_RESIZED_DIMS = (400, 300)

# ================ Prediction filtering constants ================ #
IOU_THRESH = 0.5
# add constant for min size filtering (by class?)
