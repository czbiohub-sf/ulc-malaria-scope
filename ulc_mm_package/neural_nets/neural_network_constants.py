import pathlib
from typing import Tuple, Dict

from ulc_mm_package.scope_constants import ACQUISITION_FPS

curr_dir = pathlib.Path(__file__).parent.resolve()  # Get full path


# ================ Autofocus constants ================ #
AF_PERIOD_S = 0.5
AF_PERIOD_NUM = int(AF_PERIOD_S * ACQUISITION_FPS)
AF_BATCH_SIZE = 10

AF_THRESHOLD = 2
QSIZE_THRESH = 50

AUTOFOCUS_MODEL_DIR = str(curr_dir / "autofocus_model_files/valiant-disco-119.xml")

# ================ YOGO constants ================ #
YOGO_PRED_THRESHOLD = 0.3
YOGO_MODEL_DIR = str(curr_dir / "yogo_model_files/glowing-sunset-342.xml")

YOGO_CLASS_LIST: Tuple[str, ...] = ("healthy", "ring", "schizont", "troph")
YOGO_CLASS_IDX_MAP: Dict[str, int] = {k: idx for idx, k in enumerate(YOGO_CLASS_LIST)}

YOGO_PERIOD_S = 0.1
YOGO_PERIOD_NUM = int(YOGO_PERIOD_S * ACQUISITION_FPS)
