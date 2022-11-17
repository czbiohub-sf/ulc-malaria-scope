import enum

# ================ Flowrate options ================ #
class FLOWRATE(enum.Enum):
	FAST = 15.15  # 2 frames per cell
	MEDIUM = 7.58  # 4 frames per cell
	SLOW = 3.79  # 8 frames per cell

# ================ Autobrightness constants ================ #
TOP_PERC_TARGET_VAL = 245
TOP_PERC = 0.03
TOL = 0.01
MIN_ACCEPTABLE_MEAN_BRIGHTNESS = 200

# ================ Background subtraction constants ================ #
INSIDE_BBOX_FLAG = 0

# ================ Flow control constants ================ #
NUM_IMAGE_PAIRS = 12
WINDOW_SIZE = 12
TOL_PERC = 0.1

# ================ Flow rate constants ================ #
CORRELATION_THRESH = 0.5

# You'd work backwards here...how many images do you want of the same cells?
# Let's say 2 frames/fov of cells. At 33ms/frame, we want each cell to pass
# through IMG_HEIGHT pixels in 66ms. So IMG_HEIGHT / 66s * 1000ms / 1s = 15.15 heights/second
DESIRED_FRAMES_PER_CELL = 2
MS_PER_FRAME = 33
TARGET_FLOWRATE = 1000 / (DESIRED_FRAMES_PER_CELL * MS_PER_FRAME)
 
# ================ Data storage constants ================ #
MIN_GB_REQUIRED = 50
NUM_SUBSEQUENCE = 10
SUBSEQUENCE_LENGTH = 10

# ================ Cell detection constants ================ #
RBC_THUMBNAIL_PATH = (
    "../image_processing/thumbnail.png"  # TODO better way to reference file?
)

# This value was found empirically, looking at several focal stacks with and without cells
CELLS_FOUND_THRESHOLD = 9000  # It's got to be... OVER 9000!!!!!!
CROSS_CORR_CELL_DENSITY_THRESHOLD = 6500

MIN_CELL_COUNT = 10
CELL_DENSITY_CHECK_PERIOD_S = 0.5  # How often to check cell density
CELL_DENSITY_HISTORY_LEN = 10  # Number of continuuous cell density measurements that need to be < MIN_CELL_COUNT before an exception is raised
