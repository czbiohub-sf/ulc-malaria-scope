import numpy.typing as npt

from ulc_mm_package.image_processing.focus_metrics import custom_gradient_average
from ulc_mm_package.image_processing.ewma_filtering_utils import EWMAFiltering
from ulc_mm_package.image_processing.processing_constants import (
    CLASSIC_FOCUS_EWMA_ALPHA,
    METRIC_RATIO_CUTOFF,
)


class OOF(Exception):
    def __init__(self, curr_best: int, curr_metric: int):
        msg = f"Image metric dropped from {curr_best:.3f} to {curr_metric:.3f} ({curr_metric/curr_best:.3f})%"
        super().__init__(f"{msg}")


class ClassicImageFocus:
    def __init__(
        self,
        init_img: npt.NDArray,
        ewma_alpha: float = CLASSIC_FOCUS_EWMA_ALPHA,
        cutoff_thresh: float = METRIC_RATIO_CUTOFF,
    ):
        """Classic focus metric controller.

        This class takes in an image and calculates gradient average. It adds this to an EWMA filter
        of values and it keeps track of the best seen focus so far. If the ratio of the current metric
        value to the best seen one drops below a threshold, an exception is raised.

        Initialize the function with an image, for example the first image acquired after the post-
        flowrate autofocus step is complete.

        Afterward, provide images to this function via `add_image(img)`. If the aforementioned ratio
        drops below a threshold, `add_image(img)` will raise an OOF (out of focus) exception.

        Parameters
        ----------
        init_img: npt.NDArray
        ewma_alpha: float (default = CLASSIC_FOCUS_EWMA_ALPHA)
        """

        self.a = ewma_alpha
        self.cutoff_thresh = cutoff_thresh
        self.EWMA = EWMAFiltering(self.a)

        init_metric = custom_gradient_average(init_img)
        self.EWMA.set_init_val(init_metric)
        self.curr_best = init_metric
        self.curr_metric = init_metric
        self.curr_ratio = 1.0

    def add_image(self, img: npt.NDArray):
        focus_metric = custom_gradient_average(img)
        self.curr_metric = self.EWMA.update_and_get_val(focus_metric)
        self._update()

    def _update(self):
        if self.curr_metric > self.curr_best:
            self.curr_best = self.curr_metric
        self.curr_ratio = self.curr_metric / self.curr_best

        if self.curr_ratio < self.cutoff_thresh:
            raise OOF(self.curr_best, self.curr_metric)
