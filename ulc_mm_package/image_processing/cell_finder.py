import cv2
import numpy as np

from typing import List, Optional


from ulc_mm_package.image_processing.focus_metrics import downsample_image


class LowDensity(Exception):
    pass


class NoCellsFound(Exception):
    pass


class CellFinder:
    def __init__(self, downsample_factor: int = 10, lookback_window: int = 3):
        self.downsample_factor = downsample_factor
        self.lookback_window = lookback_window
        self.motor_pos: List[int] = []
        self.sds: List[float] = []

    def add_image(self, motor_pos: int, img: np.ndarray) -> None:
        """Calculate the standard deviation of the given image (after downsmapling), store the result + motor position the image was taken at."""

        img_ds = downsample_image(img, self.downsample_factor)
        sd = np.std(img_ds)

        self.motor_pos.append(motor_pos)
        self.sds.append(sd)

    def get_cells_found_position(self) -> Optional[int]:
        """Find the motor position whose image SD stands out compared to the rest.

        Use the median-absolute-deviation and a monotonic decrease over a given lookback
        period to assess whether the peak a) has objects in it and b) is prominent relative to
        the surrounding measurements.
        """
        sds = np.asarray(self.sds, dtype=float)
        if sds.size > self.lookback_window:
            argmax = int(np.argmax(sds))
            max_val = float(sds[argmax])

            median = np.median(sds)
            mad = np.median(np.abs(sds - median))

            k = 1.4826  # Scale factor for normally distributed data
            robust_z = (max_val - median) / (k * mad)

            is_monotonically_decreasing = np.all(
                np.sign(np.diff(sds[-self.lookback_window :])) == -1
            )
            if is_monotonically_decreasing and robust_z >= 3.0:
                return self.motor_pos[argmax]

        raise NoCellsFound("No image stands out as containing cells")

    def reset(self) -> None:
        self.motor_pos = []
        self.sds = []
