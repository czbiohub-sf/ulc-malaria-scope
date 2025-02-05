#! /usr/bin/env python3

from typing import Any, List, Union
from typing_extensions import TypeAlias

import numpy as np
import numpy.typing as npt

from ulc_mm_package.utilities.lock_utils import lock_timeout
from ulc_mm_package.neural_nets.NCSModel import (
    NCSModel,
    AsyncInferenceResult,
)
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_MODEL_DIR,
    YOGO_AREA_FILTER_NORMED,
    YOGO_PRED_THRESHOLD,
    YOGO_CROP_HEIGHT_PX,
)


ClassCountResult: TypeAlias = np.ndarray


class YOGO(NCSModel):
    """
    YOGO Model

    Usage:
        >>> Y = YOGO("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image)  # our YOGO takes grayscale only so far - I'll take care of it
        >>> Y(img)
        >>> calculate_metrics()
        >>> Y(img)
        >>> calculate_metrics()
        >>> # ... eventually ...
        >>> Y.get_asyn_results()
        <
         Bounding Boxes! tensor of shape (1, 12, Sy, Sx) where Sy and Sx are grid dimensions (i.e. rows and columns)
         the second dimension (12) is the most important - it is [xc, yc, w, h, to, p_healthy, p_ring, p_schitzont, p_troph, p_gametocyte, p_wbc, p_misc],
         with each number normalized to [0,1] (and the class probabilities summing to 1)
        >
    """

    def __init__(
        self,
        model_path: str = YOGO_MODEL_DIR,
    ):
        super().__init__(model_path)

    @staticmethod
    def crop_img(img: npt.NDArray) -> npt.NDArray:
        """
        Crops the center of the image to the size expected by the model
        """
        crop_lower_bound = 386 - YOGO_CROP_HEIGHT_PX // 2
        crop_upper_bound = 386 + YOGO_CROP_HEIGHT_PX // 2 + (YOGO_CROP_HEIGHT_PX % 2)
        return img[..., crop_lower_bound:crop_upper_bound, :]

    @staticmethod
    def filter_res(res: npt.NDArray, threshold=YOGO_PRED_THRESHOLD) -> npt.NDArray:
        mask = (res[:, 4:5, :] > threshold).flatten()
        areas = (res[:, 2:3, :] * res[:, 3:4, :]).flatten()
        areas_mask = areas > YOGO_AREA_FILTER_NORMED
        return res[:, :, mask & areas_mask]

    @staticmethod
    def _format_res(res: npt.NDArray):
        bs, pred_dim, Sy, Sx = res.shape
        res.shape = (bs, pred_dim, Sy * Sx)
        return res

    def __call__(self, input_img: npt.NDArray, idxs: Any = None):
        return self.asyn(input_img, idxs)

    def syn(
        self, input_imgs: Union[npt.NDArray, List[npt.NDArray]], sort: bool = False
    ):
        return [YOGO._format_res(r) for r in super().syn(input_imgs, sort)]

    def _default_callback(self, infer_request, userdata: Any):
        res = infer_request.output_tensors[0].data[:]
        res = YOGO._format_res(res)

        with lock_timeout(self.asyn_result_lock):
            self._asyn_results.append(AsyncInferenceResult(id=userdata, result=res))
