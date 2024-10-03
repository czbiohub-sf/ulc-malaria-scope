import enum
import os
from pathlib import Path

from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_IDX_MAP


# ================ Status colors ================ #
class STATUS(enum.Enum):
    DEFAULT = "whitesmoke"
    STANDBY = "lightgray"
    IN_PROGRESS = "yellow"
    GOOD = "lightgreen"
    BAD = "lightsalmon"


# ================ Oracle error options ================ #
class ERROR_BEHAVIORS(enum.Enum):
    DEFAULT = 0
    PRECHECK = 1
    FLOWCONTROL = 2


# ================ State machine verification ================ #
NO_PAUSE_STATES = {"pause", "intermission"}

# ================ Image display size ================ #
IMG_DOWNSCALE = 2
TOOLBAR_OFFSET = 80

# ================ Infopanel values ================ #
BLANK_INFOPANEL_VAL = "---"

# ================ Thumbnail preview ================ #
MAX_THUMBNAILS = 10
CLASSES_TO_DISPLAY = ["healthy", "ring", "trophozoite", "schizont"]
CLASS_IDS = [YOGO_CLASS_IDX_MAP[class_name] for class_name in CLASSES_TO_DISPLAY]
MIN_THUMBNAIL_DISPLAY_SIZE = 55
THUMBNAIL_SPACING = 5

# ================ Dropdown menu options ================ #
SITE_LIST = [
    "Tororo, Uganda",
    "Masafu, Uganda",
    "Biohub SF",
    "DeRisi Lab",
    "Filipa Lab",
    "Goodlife Kigali",
    "Goodlife Musanze",
]

# Reorder the site list to move the environment variable specified default site to the first location
env_var = os.getenv("DEFAULT_SITE")

if env_var in SITE_LIST:
    SITE_LIST.insert(0, SITE_LIST.pop(SITE_LIST.index(env_var)))


CLINICAL_SAMPLE = "Whole blood (clinical, P. falciparum endemic)"
CULTURED_SAMPLE = "Lab cultured P. falciparum"
SAMPLE_LIST = [
    CLINICAL_SAMPLE,
    "Whole blood (donated, non-endemic)",
    CULTURED_SAMPLE,
    "Other/unknown",
    "Development (for testing use only)",
]

# ================ Experiment end conditions period ================ #
# Timeout period
TIMEOUT_PERIOD_M = 20  # minutes
TIMEOUT_PERIOD_S = TIMEOUT_PERIOD_M * 60  # seconds

# ================ Media/links ================ #
_gui_images_dir = Path(__file__).parent.resolve() / "gui_images"

ICON_PATH = str(_gui_images_dir / "CZB-logo.png")
IMAGE_INSERT_PATH = str(_gui_images_dir / "insert_infographic.png")
IMAGE_REMOVE_PATH = str(_gui_images_dir / "remove_infographic.png")
IMAGE_RELOAD_PATH = str(_gui_images_dir / "remove_infographic.png")


for image_path in (ICON_PATH, IMAGE_INSERT_PATH, IMAGE_REMOVE_PATH, IMAGE_RELOAD_PATH):
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Could not find image at {image_path}")


FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
