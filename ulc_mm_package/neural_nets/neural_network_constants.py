# ================ Autofocus constants ================ #
AF_PERIOD_S = 10
AF_BATCH_SIZE = 10
AUTOFOCUS_MODEL_DIR = "../neural_nets/autofocus_model_files/valiant-disco-119.xml"


# ================ YOGO constants ================ #
YOGO_PRED_THRESHOLD = 0.3
YOGO_MODEL_DIR = "../neural_nets/yogo_model_files/glowing-sunset-342.xml"

from typing import Tuple

YOGO_CLASS_LIST: Tuple[str,...] = ("healthy", "ring", "schizont", "troph")
