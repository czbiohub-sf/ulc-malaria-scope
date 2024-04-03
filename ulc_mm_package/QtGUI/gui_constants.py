import enum

from ulc_mm_package.image_processing.processing_constants import FLOWRATE
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
FLOWRATE_LIST = [e.name.capitalize() for e in FLOWRATE]
SITE_LIST = [
    "Tororo, Uganda",
    "Masafu, Uganda",
    "Biohub SF",
    "DeRisi Lab",
    "Filipa Lab",
]

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
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
