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
YOGOPrediction = namedtuple("YOGOPrediction", ["id", "parsed_pred"])


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
    def parse_prediction_tensor(
        prediction_tensor: npt.NDArray, img_h: int, img_w: int
    ) -> npt.NDArray:
        """Function to parse a prediction tensor.

        #TODO
        Discuss with team whether int16 is enough precision for this specific use case (i.e if this is just for displaying thumbnails)
        or whether there are other downstream applications that might require higher precision.

        IMPORTANT NOTE: The objectness tensor AND prediction probabilites are scaled by 2^16 (0 - 65,535) and then cast to an int. We lose some precision
        but mixing a float type with a tensor that's dtype=int forces the whole tensor to be a float32, which is a
        waste.

        Make sure to divide the objectness and prediction values by 2^16 before doing analysis if you expect it to be in the range 0-1!!!

        Parameters
        ----------
        prediction_tensor: np.ndarray
            The direct output tensor from a call to the YOGO model (1 * (5+NUM_CLASSES) * (Sx*Sy))
        img_h: int
        img_w: int

        Returns
        -------
        np.ndarray
                A 7 x N array representing...

                idx 0 - 3 (bounding boxes):
                    int: top left x,
                    int: top left y,
                    int: bottom right x,
                    int: bottom right y
                idx 4 (objectness)
                    int: [0-2^16] NOTE - this should be divided by 2^16 when doing analysis
                idx 5 (predictions)
                    int: Number from 0 to M, where M is the number of classes - 1) for all N objects
                    detected in the image.
                idx 6 (prediction probability)
                    float: confidence of the predicted label
        """

        filtered_pred = YOGO.filter_res(
            prediction_tensor
        ).squeeze()  # 9 x N (TODO the 9 here is variable based on number of classes, N is however many cells are predicted, but may include some double-counted/overlapping bboxes)
        xc = filtered_pred[0, :] * img_w
        yc = filtered_pred[1, :] * img_h
        pred_half_width = filtered_pred[2] / 2 * img_w
        pred_half_height = filtered_pred[3] / 2 * img_h

        tlx = np.rint(xc - pred_half_width).astype(np.uint16)
        tly = np.rint(yc - pred_half_height).astype(np.uint16)
        brx = np.rint(xc + pred_half_width).astype(np.uint16)
        bry = np.rint(yc + pred_half_height).astype(np.uint16)

        objectness = (filtered_pred[4, :] * 2**16).astype(
            np.uint16
        )  # Scaling by 2**16 so that the whole tensor doesn't have to be float64
        pred_labels = np.argmax(filtered_pred[5:, :], axis=0).astype(np.uint16)
        pred_probs = (
            filtered_pred[5:, :][pred_labels, np.arange(filtered_pred.shape[1])]
            * 2**16
        ).astype(np.uint16)

        return np.stack([tlx, tly, brx, bry, objectness, pred_labels, pred_probs])

    @staticmethod
    def parse_prediction(
        prediction: AsyncInferenceResult, img_h: int, img_w: int
    ) -> YOGOPrediction:
        """
        Given a prediction result tensor, return a cleaned up tensor of bounding boxes and associated classes.
        See `parse_prediction_tensor()` function for more details about the output.

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
            parsed_pred
                A 7 x N array representing the bounding boxes, objectness, class labels and the confidence associated with that class label

        Example
        -------
            ```
            yogo_model(img)
            ... some time later
            res = yogo_model.get_asyn_results()
            clean_res = parse_prediction(res, img_h, img_w)
            img_id = clean_res.id

            parsed_pred = clean_res.parsed_pred # Will have shape like [7 x N],
            bbox_1 = parsed_pred[:3, 0] # --> will get something like (46, 23, 92, 68)
            objectness_1 = parsed_pred[4, 0]
            predicted_class_1 = parsed_pred[5, 0] --> will get something like 2 (hot damn it's a troph!)
            predicted_class_prob = parsed_pred[6, 0] / 2^16
            ```
        """

        img_id, prediction_tensor = prediction.id, prediction.result
        parsed_pred: np.ndarray = YOGO.parse_prediction_tensor(
            prediction_tensor, img_h, img_w
        )
        return YOGOPrediction(id=img_id, parsed_pred=parsed_pred)

    def get_specific_class_from_parsed_tensor(
        parsed_prediction_tensor: npt.NDArray, class_id: int
    ) -> npt.NDArray:
        """Return all matches for the specific class ID in the parsed tensor.

        Parameters
        ----------
        parsed_prediction_tensor: npt.NDArray
            7 x N array
        class_id: int

        Returns
        -------
        np.ndarray
            Shape: 7 x N (N matches).
            Each column (i.e arr[:, i] is one predicted object).

            The 7 is the same dimension as the original prediction tensor, i.e:
                0 - bounding box top left x
                1 - bounding box top left y
                2 - bounding box bottom right x
                3 - bounding box bottom right y
                4 - objectness (0 - 2^16), divide by 2^16 to get a float between 0 - 1!!!
                5 - class ID (all columns will have the same class ID as the one you passed into this function)
                6 - probability / confidence (0 - 2^16), divide by 2^16 to get a float between 0 - 1!!!
        """

        return parsed_prediction_tensor[
            :, np.argwhere(parsed_prediction_tensor[5, :] == class_id)
        ].squeeze()

    def get_vals_greater_than_conf_thresh(
        parsed_prediction_tensor: npt.NDArray, confidence_threshold: float
    ) -> npt.NDArray:
        """Given a prediction tensor, return all the columns which have a class prediction
        probability/confidence strictly greater than the given threshold.

        Parameters
        ----------
        parsed_prediction_tensor: npt.NDArray
            7 x N array
        confidence_threshold: float [0 - 1]

        Returns
        -------
        np.ndarray
            7 x M (M <= N)
        """

        confidence_threshold = np.rint(2**16 * confidence_threshold).astype(np.uint16)
        mask = parsed_prediction_tensor[6, :] > confidence_threshold
        return parsed_prediction_tensor[:, mask]

    def get_vals_less_than_conf_thresh(
        parsed_prediction_tensor: npt.NDArray, confidence_threshold: float
    ):
        """Given a prediction tensor, return all the columns which have a class prediction
        probability/confidence strictly less than the given threshold.

        Parameters
        ----------
        parsed_prediction_tensor: npt.NDArray
            7 x N array
        confidence_threshold: float [0 - 1]

        Returns
        -------
        np.ndarray
            7 x M (M <= N)
        """

        confidence_threshold = np.rint(2**16 * confidence_threshold).astype(np.uint16)
        mask = parsed_prediction_tensor[6, :] < confidence_threshold
        return parsed_prediction_tensor[:, mask]

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
