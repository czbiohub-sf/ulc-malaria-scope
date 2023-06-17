#! /usr/bin/env python3


import numpy as np
import numpy.typing as npt

from collections import namedtuple
from typing import Any, List, Union
from typing_extensions import TypeAlias

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
YOGOPrediction = namedtuple("YOGOPrediction", ["id", "bboxes_and_classes"])


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
        class_preds = np.argmax(filtered_res[0, 5:, :], axis=0)
        unique, counts = np.unique(class_preds, return_counts=True)
        # this dict (raw_counts) will be missing a given class if that class isn't predicted at all
        # this may be confusing and a pain to handle, so just handle it on our side
        raw_counts = dict(zip(unique, counts))
        class_counts = np.array(
            [raw_counts.get(i, 0) for i in range(num_classes)], dtype=int
        )
        return class_counts

    @staticmethod
    def parse_prediction(
        prediction: AsyncInferenceResult, img_h: int, img_w: int
    ) -> YOGOPrediction:
        """
        Given a prediction result tensor, return a cleaned up tensor of bounding boxes and associated classes.

        Parameters
        ----------
        prediction: AsyncInferenceResult
            A result from a YOGO(img) call
        img_h: int
        img_w: int

        Returns
        -------
        YOGOPrediction
            img_id - id that you passed in
            bboxes_and_classes
                A 5 x N array representing the bounding boxes (top left x, top left y, bottom right x, bottom right y)
                and the predictions (number from 0 to M, where M is the number of classes - 1) for all N objects
                detected in the image.

        Example
        -------
            ```
            yogo_model(img)
            ... some time later
            res = yogo_model.get_asyn_results()
            bboxes_and_classes = parse_prediction(res, img_h, img_w).bboxes_and_classes  # Will have shape like [5 x N],
            bbox1 = bboxes_and_classes[:4, 0] # --> will get something like (46, 23, 92, 68)
            predicted_class1 = bboxes_and_classes[5, 0] --> will get something like 2 (hot damn it's a troph!)
            ```
        """

        img_id, res = prediction.id, prediction.result
        filtered_pred = YOGO.filter_res(
            res
        ).squeeze()  # 9 x N (TODO the 9 here is variable based on number of classes, N is however many cells are predicted, but may include some double-counted/overlapping bboxes)
        xc = filtered_pred[0, :] * img_w
        yc = filtered_pred[1, :] * img_h
        pred_half_width = filtered_pred[2] / 2 * img_w
        pred_half_height = filtered_pred[3] / 2 * img_h

        tlx = xc - pred_half_width
        tly = yc - pred_half_height
        brx = xc + pred_half_width
        bry = xc + pred_half_height
        preds = np.argmax(filtered_pred[5:, :], axis=0)

        bboxes_and_classes = np.stack([tlx, tly, brx, bry, preds])
        return YOGOPrediction(id=img_id, bboxes_and_classes=bboxes_and_classes)

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
