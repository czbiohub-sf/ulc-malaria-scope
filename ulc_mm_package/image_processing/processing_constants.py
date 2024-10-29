import enum

from pathlib import Path

from ulc_mm_package.scope_constants import SIMULATION


# ================ Flowrate options ================ #
class FLOWRATE(enum.Enum):
    FAST = 15.15  # 2 frames per cell
    MEDIUM = 7.58  # 4 frames per cell
    SLOW = 3.79  # 8 frames per cell


# ================ Data storage figure locations ================ #
SUMMARY_FOLDER = "summary_report"
PARASITEMIA_VIS_FILE = "parasitemia.jpg"

# ================ Autobrightness constants ================ #
TOP_PERC_TARGET_VAL = 235
TOP_PERC = 0.03
TOL = 0.01
MIN_ACCEPTABLE_MEAN_BRIGHTNESS = 200
PERIODIC_AB_PERIOD_NUM_FRAMES = 60  # At 30 fps, this is roughly once per 2 seconds

# Autobrightness PID constants
AB_PID_KP = 0.001
AB_PID_KI = 0.0
AB_PID_KD = 0.0001
INTEGRAL_WINDUP_BOUND = 10

# ================ Background subtraction constants ================ #
INSIDE_BBOX_FLAG = 0

# ================ Flow control constants ================ #
FLOW_CONTROL_EWMA_ALPHA = 0.05
TOL_PERC = 0.1
FAILED_CORR_PERC_TOLERANCE = 0.75

# Factor by which to multiply the ewma feebdack adjustment delay (in frames) to set the window size
# of the past measurements to check for failed xcorrs.
MIN_NUM_XCORR_FACTOR = 10

# ================ Flow rate constants ================ #
CORRELATION_THRESH = 0.3
TARGET_FLOWRATE = FLOWRATE.MEDIUM

# ================ Classic image focus metric constants ================ #
CLASSIC_FOCUS_EWMA_ALPHA = 0.1
METRIC_RATIO_CUTOFF = 0.75
CLASSIC_FOCUS_FRAME_THROTTLE = 15

# ================ Data storage constants ================ #
if SIMULATION:
    MIN_GB_REQUIRED = 0.1  # 100 MB
else:
    MIN_GB_REQUIRED = 50
NUM_SUBSEQUENCES = 10
SUBSEQUENCE_LENGTH = 10

# ================ Cell detection constants ================ #
_RBC_THUMBNAIL_PATH = Path(__file__).parent.resolve() / "thumbnail.png"
if not _RBC_THUMBNAIL_PATH.exists():
    raise FileNotFoundError(
        "RBC_THUMBNAIL_PATH (image_processing/thumbnail.png) does not exist"
    )
RBC_THUMBNAIL_PATH = str(_RBC_THUMBNAIL_PATH)

# This value was found empirically, looking at several focal stacks with and without cells
CELLS_FOUND_THRESHOLD = 9001  # https://tinyurl.com/ykxu66zw
MIN_POINTS_ABOVE_THRESH = 2

MIN_CELL_COUNT = 5
CELL_DENSITY_CHECK_PERIOD_S = 0.2  # How often to check cell density
CELL_DENSITY_HISTORY_LEN = 40  # Number of continuuous cell density measurements that need to be < MIN_CELL_COUNT before an exception is raised
