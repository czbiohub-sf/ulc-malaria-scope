from __future__ import annotations
from typing import NamedTuple, List

import numpy as np
import numpy.typing as npt

from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.neural_network_constants import IMG_RESIZED_DIMS

DEFAULT_W, DEFAULT_H = IMG_RESIZED_DIMS


class SinglePredictedObject(NamedTuple):
    img_id: int
    parsed: npt.NDArray  # 7 x 1
    conf: int  # np.uint16 (same as parsed[6])

    def __lt__(self, other: SinglePredictedObject):
        return self.conf < other.conf


def parse_prediction_tensor(
    prediction_tensor: npt.NDArray, img_h: int = DEFAULT_H, img_w: int = DEFAULT_W
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
    ).squeeze()  # 12 x N (TODO the 9 here is variable based on number of classes, N is however many cells are predicted, but may include some double-counted/overlapping bboxes)
    xc = filtered_pred[0, :] * img_w
    yc = filtered_pred[1, :] * img_h
    pred_half_width = filtered_pred[2] / 2 * img_w
    pred_half_height = filtered_pred[3] / 2 * img_h

    tlx = np.rint(xc - pred_half_width).astype(np.uint16)
    tly = np.rint(yc - pred_half_height).astype(np.uint16)
    brx = np.rint(xc + pred_half_width).astype(np.uint16)
    bry = np.rint(yc + pred_half_height).astype(np.uint16)

    objectness = convert_float_to_uint16(
        filtered_pred[4, :]
    )  # Scaling by 2**16 so that the whole tensor doesn't have to be float64
    pred_labels = np.argmax(filtered_pred[5:, :], axis=0).astype(np.uint16)
    pred_probs = convert_float_to_uint16(
        filtered_pred[5:, :][pred_labels, np.arange(filtered_pred.shape[1])]
    )

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
            4 - objectness (0 - 2^16), divide by 2^16 to get a float between 0 - 1!!!
            5 - class ID (all columns will have the same class ID as the one you passed into this function)
            6 - probability / confidence (0 - 2^16), divide by 2^16 to get a float between 0 - 1!!!
    """

    mask = parsed_prediction_tensor[5, :] == class_id
    return parsed_prediction_tensor[:, mask]


def convert_float_to_uint16(val: float) -> np.uint16:
    """Convert a float between 0 - 1 to an uint16 (between 0 - 65,535).

    Parameters
    ----------
    val: float [0 - 1] / np.ndarray[float32]

    Returns
    -------
    uint16 [0 - 65,535]
    """

    return np.rint(val * 2**16).astype(np.uint16)


def get_col_ids_for_matching_class_and_above_conf_thresh(
    parsed_prediction_tensor: npt.NDArray,
    class_id: int,
    confidence_threshold: np.uint16,
) -> List[int]:
    """Get the column ids of the passed-in prediction tensor which have
    the given class_id and are above the given confidence threshold.

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray
        7 x N array
    class_id: int
    confidence_threshold: uint16 [0 - 65535]

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
    confidence_threshold: np.uint16,
) -> List[int]:
    """Get the column ids of the passed-in prediction tensor which have
    the given class_id and are below the given confidence threshold.

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray
        7 x N array
    class_id: int
    confidence_threshold: uint16 [0 - 65535]

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
    parsed_prediction_tensor: npt.NDArray, confidence_threshold: np.uint16
) -> npt.NDArray:
    """Given a prediction tensor, return all the columns which have a class prediction
    probability/confidence strictly greater than the given threshold.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray
        7 x N array
    confidence_threshold: uint16 [0 - 65535]

    Returns
    -------
    np.ndarray
        7 x M (M <= N)
    """

    mask = parsed_prediction_tensor[6, :] > confidence_threshold
    return parsed_prediction_tensor[:, mask]


def get_vals_less_than_conf_thresh(
    parsed_prediction_tensor: npt.NDArray, confidence_threshold: np.uint16
) -> npt.NDArray:
    """Given a prediction tensor, return all the columns which have a class prediction
    probability/confidence strictly less than the given threshold.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray
        7 x N array
    confidence_threshold: uint16 [0 - 65535]

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
    col_idxs: List[int],
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
