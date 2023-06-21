import enum

from ulc_mm_package.image_processing.processing_constants import FLOWRATE


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
CLASSES_TO_DISPLAY = ["Healthy", "Ring", "Troph", "Schizont"]
CLASS_IDS = [0, 1, 2, 3]
MIN_THUMBNAIL_DISPLAY_SIZE = 55
THUMBNAIL_SPACING = 5

# ================ Dropdown menu options ================ #
FLOWRATE_LIST = [e.name.capitalize() for e in FLOWRATE]
SITE_LIST = ["Tororo, Uganda", "Biohub SF", "DeRisi Lab"]

# ================ Experiment timeout period ================ #
TIMEOUT_PERIOD_M = 20  # minutes
TIMEOUT_PERIOD_S = TIMEOUT_PERIOD_M * 60  # seconds

# ================ Media/links ================ #
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
