import enum

from ulc_mm_package.scope_constants import SIMULATION
from ulc_mm_package.image_processing.processing_constants import FLOWRATE

# ================ Status colors ================ #
class STATUS(enum.Enum):
    STANDBY = "lightgray"
    IN_PROGRESS = "yellow"
    GOOD = "lightgreen"
    BAD = "red"


# ================ Dropdown menu options ================ #
FLOWRATE_LIST = [e.name.capitalize() for e in FLOWRATE]
SITE_LIST = ["Tororo, Uganda", "Biohub SF", "DeRisi Lab"]

# ================ FPS constants ================ #
ACQUISITION_PERIOD = 1000.0 / 60.0
LIVEVIEW_PERIOD = 1000

# ================ Hardware update period ================ #
# TH sensor update period
TH_PERIOD = 5

# ================ Media/links ================ #
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
