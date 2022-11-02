import enum

# ================ Status colors ================ #
class STATUS(enum.Enum):
    STANDBY = "lightgray"
    IN_PROGRESS = "yellow"
    GOOD = "lightgreen"
    BAD = "red"

# ================ Dropdown menu options ================ #
PROTOCOL_LIST = ["Default"]
SITE_LIST = ["Tororo, Uganda"]

# ================ FPS constants ================ #
ACQUISITION_PERIOD = 1000.0 / 30.0
LIVEVIEW_PERIOD = 1000

# ================ Experiment timeout ================ #
MAX_FRAMES = 40000  # Rounded up from 20 minutes of data at 30 FPS
# For testing
# MAX_FRAMES = 10

# ================ Media/links ================ #
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)
