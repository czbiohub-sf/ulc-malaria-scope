import enum

# Status color indicators
class STATUS(enum.Enum):
    STANDBY = "lightgray"
    GOOD = "lightgreen"
    BAD = "red"


# Default info panel metadata
INFOPANEL_METADATA = {
    "state" : "--",
    "frame" : None, 
    "brightness" : "--",
    "brightness_status" : STATUS.STANDBY,
    "focus" : "--",
    "focus_status" : STATUS.STANDBY,
    "flowrate" : "--",
    "flowrate_status" : STATUS.STANDBY,
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