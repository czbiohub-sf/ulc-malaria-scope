from pathlib import Path
from typing import Tuple, Dict, List

from ulc_mm_package.scope_constants import ACQUISITION_FPS, CAMERA_SELECTION

curr_dir = Path(__file__).parent.resolve()  # Get full path


# ================ Autofocus constants ================ #
AF_PERIOD_S = 0.5
AF_PERIOD_NUM = int(
    AF_PERIOD_S * ACQUISITION_FPS
)  # Used for periodic (ie. EWMA) autofocus
AF_BATCH_SIZE = 10  # Used for single shot autofocus

AF_THRESHOLD = 2
AF_QSIZE = 10  # For AF_PERIOD_S = 0.5, we have a max delay of 5 sec

AUTOFOCUS_MODEL_NAME = "cosmic-waterfall-550"
AUTOFOCUS_MODEL_DIR = str(
    curr_dir / "autofocus_model_files" / AUTOFOCUS_MODEL_NAME / "best.xml"
)

if not Path(AUTOFOCUS_MODEL_DIR).exists():
    raise FileNotFoundError("autofocus model not found")

# ================ YOGO constants ================ #
YOGO_AREA_FILTER = 1200
YOGO_AREA_FILTER_NORMED = YOGO_AREA_FILTER / (
    CAMERA_SELECTION.IMG_HEIGHT * CAMERA_SELECTION.IMG_WIDTH
)
YOGO_PRED_THRESHOLD = 0.5
YOGO_CONF_THRESHOLD = 0.9
YOGO_MODEL_NAME = "elated-smoke-4492"
YOGO_MODEL_DIR = str(curr_dir / "yogo_model_files" / YOGO_MODEL_NAME / "best.xml")

if not Path(YOGO_MODEL_DIR).exists():
    raise FileNotFoundError("yogo model not found")

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
CLASS_IDS_FOR_THUMBNAILS: List[int] = [
    YOGO_CLASS_IDX_MAP["healthy"],
    YOGO_CLASS_IDX_MAP["ring"],
    YOGO_CLASS_IDX_MAP["trophozoite"],
    YOGO_CLASS_IDX_MAP["schizont"],
    YOGO_CLASS_IDX_MAP["gametocyte"],
    YOGO_CLASS_IDX_MAP["wbc"],
]

# best way to find this number is to look for input shape in the model definition xml file
YOGO_CROP_HEIGHT_PX: int = 193

# ================ Image size constants ================ #
IMG_RESIZED_DIMS = (400, 300)

# ================ Prediction filtering constants ================ #
IOU_THRESH = 0.5
# add constant for min size filtering (by class?)
