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
    YOGO_PRED_THRESHOLD,
)


ClassCountResult: TypeAlias = np.ndarray


def extract_confidences(filtered_res: npt.NDArray) -> npt.NDArray:
    """
    Returns confidence values only (ie. isolates confidence from bounding box info)
    """
    return filtered_res[0, 5:, :]


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
         with each number normalized to [0,1]
        >

    """

    def __init__(
        self,
        model_path: str = YOGO_MODEL_DIR,
    ):
        super().__init__(model_path)

    @staticmethod
    def filter_res(res: npt.NDArray, threshold=YOGO_PRED_THRESHOLD) -> npt.NDArray:
        mask = (res[:, 4:5, :] > threshold).flatten()
        return res[:, :, mask]

    @staticmethod
    def _format_res(res: npt.NDArray):
        bs, pred_dim, Sy, Sx = res.shape
        res.shape = (bs, pred_dim, Sy * Sx)
        return res

    @staticmethod
    def class_instance_count(filtered_res: npt.NDArray) -> ClassCountResult:
        """
        ClassCountResult mapping the class (represented as an integer) to its count
        for the given prediction
        """
        bs, pred_dim, num_predicted = filtered_res.shape
        num_classes = pred_dim - 5
        class_preds = np.argmax(extract_confidences(filtered_res), axis=0)
        unique, counts = np.unique(class_preds, return_counts=True)
        # this dict (raw_counts) will be missing a given class if that class isn't predicted at all
        # this may be confusing and a pain to handle, so just handle it on our side
        raw_counts = dict(zip(unique, counts))
        class_counts = np.array(
            [raw_counts.get(i, 0) for i in range(num_classes)], dtype=int
        )
        return class_counts

    @staticmethod
    def sort_confidences(filtered_res: npt.NDArray) -> List[npt.NDArray]:
        """
        Return compiled confidences for each class
        """
        bs, pred_dim, num_predicted = filtered_res.shape
        num_classes = pred_dim - 5
        class_confidences = extract_confidences(filtered_res)
        class_preds = np.argmax(class_confidences, axis=0)

        return [
            class_confidences[class_idx, class_preds == class_idx]
            for class_idx in range(num_classes)
        ]

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
