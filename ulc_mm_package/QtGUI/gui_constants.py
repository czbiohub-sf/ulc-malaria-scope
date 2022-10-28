<<<<<<< HEAD
import enum

# ================ Status colors ================ #
class STATUS(enum.Enum):
    STANDBY = "lightgray"
    GOOD = "lightgreen"
    BAD = "red"
    IN_PROGRESS = "yellow"


# ================ Metadata ================ #
INFOPANEL_METADATA = {
    "state" : "--",
    "im_counter" : None, 
    "terminal_msg" : "",
    "brightness" : "--",
    "brightness_status" : STATUS.STANDBY,
    "focus" : "--",
    "focus_status" : STATUS.STANDBY,
    "flowrate" : None,
    "flowrate_status" : STATUS.STANDBY,
    }     

INFOPANEL_METADATA_KEYS = [
    "im_counter",
    # "brightness",
    # "focus",
    "flowrate",
]

IMAGE_METADATA = {
        "im_counter" : 0,
        "timestamp" : None,
        "motor_pos" : None,
        "pressure_hpa" : None,
        "syringe_pos" : None,
        "flowrate" : "--",
        "temperature" : None,
        "humidity" : None,
    }

# ================ Dropdown menu options ================ #
PROTOCOL_LIST = ["Default"]
SITE_LIST = ["Tororo, Uganda"]


# ================ FPS constants ================ #
ACQUISITION_PERIOD = 1000.0 / 30.0
LIVEVIEW_PERIOD = 1000

# ================ Experiment timeout ================ #
MAX_FRAMES = 100

# ================ Media/links ================ #
ICON_PATH = "gui_images/CZB-logo.png"

FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)