import pathlib

curr_dir = pathlib.Path(".")

# ================ Autofocus constants ================ #
AF_PERIOD_S = 10
AF_BATCH_SIZE = 10
AUTOFOCUS_MODEL_DIR = str(curr_dir / "autofocus_model_files/valiant-disco-119.xml")


# ================ YOGO constants ================ #
YOGO_PRED_THRESHOLD = 0.3
YOGO_MODEL_DIR = str(curr_dir / "yogo_model_files/glowing-sunset-342.xml")

from typing import Tuple, Dict

YOGO_CLASS_LIST: Tuple[str, ...] = ("healthy", "ring", "schizont", "troph")
YOGO_CLASS_IDX_MAP: Dict[str, int] = {k: idx for idx, k in enumerate(YOGO_CLASS_LIST)}

YOGO_PERIOD_S = 0.1
