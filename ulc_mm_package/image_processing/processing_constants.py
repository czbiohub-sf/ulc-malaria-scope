# ================ Autobrightness constants ================ #
TOP_PERC_TARGET_VAL = 245
TOP_PERC = 0.03
TOL = 0.01

# ================ Background subtraction constants ================ #
INSIDE_BBOX_FLAG = 0

# ================ Flow control constants ================ #
NUM_IMAGE_PAIRS = 12
WINDOW_SIZE = 12
TOL_PERC = 0.1

# ================ Flow rate constants ================ #
CORRELATION_THRESH = 0.5

# TODO: Determine an actual value for this.
# You'd work backwards here...how many images do you want of the same cells?
# Let's say 2 frames/fov of cells. At 33ms/frame, we want each cell to pass
# through IMG_HEIGHT pixels in 66ms. So IMG_HEIGHT / 66s * 1000ms / 1s = 15.15 heights/second
TARGET_FLOWRATE = 15 # In units of IMG_HEIGHT pixels/second.

# ================ Data storage constants ================ #
DEFAULT_SSD = "/media/pi/"

EXPERIMENT_METADATA_KEYS = [
        "operator_id",
        "participant_id",
        "flowcell_id",
        "protocol",
        "site",
        "notes",
        # "scope", # TO BE ADDED
        "camera", # AVT / Basler
        "target_flowrate",
        "exposure",
        "target_flowrate",
        "target_brightness",
    ]

PER_IMAGE_METADATA_KEYS = [
        "im_counter",
        "timestamp",
        "motor_pos",
        "pressure_hpa",
        "syringe_pos",
        "flowrate",
        "temperature",
        "humidity",
    ]

# ================ Cell detection constants ================ #
RBC_THUMBNAIL_PATH = "../image_processing/thumbnail.png" #TODO better way to reference file?

# This value was found empirically, looking at several focal stacks with and without cells
CELLS_FOUND_THRESHOLD = 9000 # It's got to be... OVER 9000!!!!!!

MIN_CELL_COUNT = 10