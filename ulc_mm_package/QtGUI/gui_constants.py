import enum

# Status color indicators
class STATUS(enum.Enum):
    STANDBY = "lightgray"
    GOOD = "lightgreen"
    BAD = "red"
    IN_PROGRESS = "yellow"


# Default info panel metadata
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

# Experiment form dropdown menu selection
PROTOCOL_LIST = ["Default"]
SITE_LIST = ["Tororo, Uganda"]

# FPS rate
ACQUISITION_PERIOD = 1000.0 / 30.0
LIVEVIEW_PERIOD = 1000

# Run duration
MAX_FRAMES = 40000 # Rounded up, assuming 20 minutes of data at 30 FPS

# Window icon
ICON_PATH = "gui_images/CZB-logo.png"

# SSD directory
DEFAULT_SSD = "/media/pi/"
ALT_SSD = "sim_media/pi/"

# Flowcell QC Form
FLOWCELL_QC_FORM_LINK = (
    "https://docs.google.com/forms/d/16pOE3TAvOMZG4Yuu3ef73knGYKRdZfXSxg5vZlsR-AM/edit"
)