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
    YN = 2


# ================ Infopanel values ================ #
BLANK_INFOPANEL_VAL = "---"

# ================ Dropdown menu options ================ #
FLOWRATE_LIST = [e.name.capitalize() for e in FLOWRATE]
SITE_LIST = ["Tororo, Uganda", "Biohub SF", "DeRisi Lab"]

# ================ FPS constants ================ #
ACQUISITION_PERIOD = 1000.0 / 60.0
LIVEVIEW_PERIOD = 1000

# ================ Hardware update period ================ #
# TH sensor update period
TH_PERIOD = 5

# ================ Experiment timeout period ================ #
TIMEOUT_PERIOD_M = 20  # minutes
TIMEOUT_PERIOD_S = TIMEOUT_PERIOD_M * 60  # seconds

# ================ Media/links ================ #
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
