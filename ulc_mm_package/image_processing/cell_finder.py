from typing import List
import numpy as np
import cv2
from ulc_mm_package.image_processing.processing_constants import RBC_THUMBNAIL_PATH, CELLS_FOUND_THRESHOLD

def downSampleImage(img: np.ndarray, scale_factor: int) -> np.ndarray:
    """Downsamples an image by `scale_factor`"""
    h, w = img.shape
    return cv2.resize(img, (w // scale_factor, h // scale_factor))

class CellFinder:
    def __init__(self, template_path: str=RBC_THUMBNAIL_PATH, downsample_factor: int=10):
        self.thumbnail = downSampleImage(cv2.imread(template_path, 0), downsample_factor)
        self.downsample_factor = downsample_factor

    def getMaxCrossCorrelationVal(self, img: np.ndarray) -> float:
        """Template matching using the RBC thumbnail and the given image

        Returns
        -------
        float: 
            Max value of the 2D cross-correlation
        """

        img_ds = downSampleImage(img, self.downsample_factor)
        res = cv2.matchTemplate(img_ds, self.thumbnail, cv2.TM_CCOEFF)
        return np.max(res)

    def checkForCells(self, corr_val: float) -> bool:
        """Check if a 2D correlation value exceeds the threshold for cell detection."""
        if corr_val >= CELLS_FOUND_THRESHOLD:
            return True
        else:
            return False