import platform


EDGETPU_SHARED_LIB = {
    'Linux': 'libedgetpu.so.1',
    'Darwin': 'libedgetpu.1.dylib',
    'Windows': 'edgetpu.dll'
}[platform.system()]
LUMI_CSV_COLUMNS = [
    'image_id', 'xmin', 'xmax', 'ymin', 'ymax', 'label', 'prob']
DEFAULT_CONFIDENCE = 0.4
DEFAULT_FILTER_AREA = 22680
DEFAULT_INFERENCE_COUNT = 1
DEFAULT_IMAGE_FORMAT = ".jpg"
