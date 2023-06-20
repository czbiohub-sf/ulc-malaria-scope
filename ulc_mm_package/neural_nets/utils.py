from __future__ import annotations
from typing import NamedTuple, List, Tuple, no_type_check

import numpy as np
import numpy.typing as npt

from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.neural_network_constants import IMG_RESIZED_DIMS

DEFAULT_W, DEFAULT_H = IMG_RESIZED_DIMS
DTYPE = np.float16


class SinglePredictedObject(NamedTuple):
    img_id: int
    parsed: npt.NDArray  # 7 x 1
    conf: DTYPE

    @no_type_check
    def __lt__(self, other: SinglePredictedObject):
        return self.conf < other.conf


def parse_prediction_tensor(
    prediction_tensor: npt.NDArray, img_h: int = DEFAULT_H, img_w: int = DEFAULT_W
) -> npt.NDArray:
    """Function to parse a prediction tensor.

    Parameters
    ----------
    prediction_tensor: np.ndarray
        The direct output tensor from a call to the YOGO model (1 * (5+NUM_CLASSES) * (Sx*Sy))
    img_h: int
    img_w: int

    Returns
    -------
    np.ndarray (dtype=DTYPE)
            A 7 x N array representing...

            idx 0 - 3 (bounding boxes):
                int: top left x,
                int: top left y,
                int: bottom right x,
                int: bottom right y
            idx 4 (objectness)
                float: [0 - 1]
            idx 5 (predictions)
                int: Number from 0 to M, where M is the number of classes - 1) for all N objects
                detected in the image.
            idx 6 (prediction probability)
                float: [0 - 1]
                confidence of the predicted label
    """

    filtered_pred = YOGO.filter_res(prediction_tensor).squeeze()  # (5+NUM_CLASSES) x N
    xc = filtered_pred[0, :] * img_w
    yc = filtered_pred[1, :] * img_h
    pred_half_width = filtered_pred[2] / 2 * img_w
    pred_half_height = filtered_pred[3] / 2 * img_h

    tlx = np.rint(xc - pred_half_width).astype(DTYPE)
    tly = np.rint(yc - pred_half_height).astype(DTYPE)
    brx = np.rint(xc + pred_half_width).astype(DTYPE)
    bry = np.rint(yc + pred_half_height).astype(DTYPE)

    objectness = filtered_pred[4, :].astype(DTYPE)
    pred_labels = np.argmax(filtered_pred[5:, :], axis=0).astype(np.uint8)
    pred_probs = filtered_pred[5:, :][
        pred_labels, np.arange(filtered_pred.shape[1])
    ].astype(DTYPE)

    return np.stack([tlx, tly, brx, bry, objectness, pred_labels, pred_probs])


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
            4 - objectness (0 - 1)
            5 - class ID (all columns will have the same class ID as the one you passed into this function)
            6 - probability / confidence (0 - 1)
    """

    mask = parsed_prediction_tensor[5, :] == class_id
    return parsed_prediction_tensor[:, mask]


def scale_bbox_vals(
    parsed_prediction_tensor: npt.NDArray, scale_h: float, scale_w: float
) -> None:
    """Scale the bounding box locations by the given scale factors.
    NOTE: this modifies the array existing array!

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray (7 x N)
    scale_h: float
    scale_w: float

    Returns
    -------
    np.ndarray
        7 x N array with the indices [0-3] (corresponding to the bounding box corners) scaled by the given scale factors.
    """

    parsed_prediction_tensor[0, :] = np.rint(parsed_prediction_tensor[0, :] * scale_w)
    parsed_prediction_tensor[1, :] = np.rint(parsed_prediction_tensor[1, :] * scale_h)
    parsed_prediction_tensor[2, :] = np.rint(parsed_prediction_tensor[2, :] * scale_w)
    parsed_prediction_tensor[3, :] = np.rint(parsed_prediction_tensor[3, :] * scale_h)


def get_col_ids_for_matching_class_and_above_conf_thresh(
    parsed_prediction_tensor: npt.NDArray,
    class_id: int,
    confidence_threshold: DTYPE,
) -> Tuple[np.ndarray]:
    """Get the column ids of the passed-in prediction tensor which have
    the given class_id and are above the given confidence threshold.

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray
        7 x N array
    class_id: int
    confidence_threshold: float [0 - 1]

    Returns
    -------
    List[int]
        List of column IDs of the original parsed_prediction_tensor which
        have the matching class_id and confidence threshold strictly greater than the one
        passed in.
    """

    mask = np.logical_and(
        parsed_prediction_tensor[5, :] == class_id,
        parsed_prediction_tensor[6, :] > confidence_threshold,
    )
    return np.nonzero(mask)


def get_col_ids_for_matching_class_and_below_conf_thresh(
    parsed_prediction_tensor: npt.NDArray,
    class_id: int,
    confidence_threshold: DTYPE,
) -> Tuple[np.ndarray]:
    """Get the column ids of the passed-in prediction tensor which have
    the given class_id and are below the given confidence threshold.

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray
        7 x N array
    class_id: int
    confidence_threshold: float [0 - 1]

    Returns
    -------
    List[int]
        List of column IDs of the original parsed_prediction_tensor which
        have the matching class_id and confidence threshold strictly below than the one
        passed in.
    """

    mask = np.logical_and(
        parsed_prediction_tensor[5, :] == class_id,
        parsed_prediction_tensor[6, :] < confidence_threshold,
    )
    return np.nonzero(mask)


def get_vals_greater_than_conf_thresh(
    parsed_prediction_tensor: npt.NDArray, confidence_threshold: DTYPE
) -> npt.NDArray:
    """Given a prediction tensor, return all the columns which have a class prediction
    probability/confidence strictly greater than the given threshold.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray
        7 x N array
    confidence_threshold: DTYPE

    Returns
    -------
    np.ndarray
        7 x M (M <= N)
    """

    mask = parsed_prediction_tensor[6, :] > confidence_threshold
    return parsed_prediction_tensor[:, mask]


def get_vals_less_than_conf_thresh(
    parsed_prediction_tensor: npt.NDArray, confidence_threshold: DTYPE
) -> npt.NDArray:
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

    mask = parsed_prediction_tensor[6, :] < confidence_threshold
    return parsed_prediction_tensor[:, mask]


def get_individual_prediction_objs_from_parsed_tensor(
    img_id: int,
    parsed_prediction_tensor: npt.NDArray,
    col_idxs: Tuple[npt.NDArray],
    flip_conf_sign: bool = False,
) -> List[SinglePredictedObject]:
    """Get a list of individual prediction objects given a prediction tensor and
    a list of specified columns.

    Each SinglePredictedObject has an image ID (the image to which the prediction belongs)
    and a row of details about that predicted object (bounding box, objectness, class id and confidence). (7x1 array)

    Parameters
    ----------
    img_id: int
    parsed_prediction_tensor: npt.NDArray
    col_idxs: List[int]
    flip_conf_sign: bool
        This is only here because Python doesn't have a default max heap implementation, so it's easier to
        flip the sign on the confidence value and use the min heap. This flipped sign confidence value is only
        used internally within the heap when doing comparisons. The original confidence value is untouched.

    Returns
    -------
    List[SinglePredictedObject]
    """

    flip = -1 if flip_conf_sign else 1
    return [
        SinglePredictedObject(
            img_id,
            parsed_prediction_tensor[:, i],
            conf=parsed_prediction_tensor[6, i] * flip,
        )
        for i in col_idxs
    ]
