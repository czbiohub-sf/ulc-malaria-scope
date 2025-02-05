from __future__ import annotations
from pathlib import Path
from typing import NamedTuple, List, Tuple, no_type_check, Dict
from typing_extensions import TypeAlias
import xml.etree.ElementTree as ET

import cv2
import zarr
import numpy as np
import numpy.typing as npt
from numba import njit

from ulc_mm_package.scope_constants import MAX_THUMBNAILS_SAVED_PER_CLASS
from ulc_mm_package.neural_nets.neural_network_constants import (
    IMG_RESIZED_DIMS,
    CLASS_IDS_FOR_THUMBNAILS,
    YOGO_CLASS_IDX_MAP,
    YOGO_CLASS_LIST,
    YOGO_CONF_THRESHOLD,
    YOGO_AREA_FILTER,
    YOGO_CROP_HEIGHT_PX,
)
from ulc_mm_package.neural_nets.YOGOInference import YOGO

NUM_CLASSES = len(YOGO_CLASS_LIST)
DEFAULT_W, DEFAULT_H = IMG_RESIZED_DIMS
DTYPE: TypeAlias = np.float32


class Thumbnail(NamedTuple):
    img_crop: npt.NDArray  # n x m array (different for every thumbnail)
    confidence: float  # value between [0-1]


class SinglePredictedObject(NamedTuple):
    parsed: npt.NDArray  # 8+NUM_CLASSES x 1
    conf: DTYPE

    @no_type_check
    def __lt__(self, other: SinglePredictedObject):
        """Compare the confidences, if there is a tie, then compare the image ids.

        This has the effect that older image id entries will be bubbled up
        to the top of the min priority queue, meaning newer entries will get
        cycled in. Users will get to see more recent thumbnails.
        """

        return (self.conf, self.parsed[0]) < (other.conf, other.parsed[0])

    def __repr__(self):
        """Print object, helpful for debugging"""
        return f"img_id: {self.parsed[0]} - conf: {self.conf}\n"


def get_output_layer_dims_from_xml(xml_path: Path) -> Tuple[int, int]:
    """Get the output layer dimensions from the model's xml file.

    Note: I am unsure how reliably formatted the generated `.xml` file format is,
    however it works for the n=2 files I tried (graceful-smoke and fine-voice).

    Parameters
    ----------
    xml_path: Path

    Returns
    -------
    Tuple[int, int]
        Sx, sy dimensions of the YOGO output
    """

    tree = ET.parse(xml_path)
    root = tree.getroot()

    sx = int(root[0][-1][0][0][-1].text)  # type: ignore
    sy = int(root[0][-1][0][0][-2].text)  # type: ignore

    return (sx, sy)


@njit(cache=True)
def _parse_prediction_tensor(
    img_id: int,
    prediction_tensor: np.ndarray,
    img_h: int = DEFAULT_H,
    img_w: int = DEFAULT_W,
    DTYPE=np.float32,
) -> Tuple[
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
    npt.NDArray,
]:
    """Function to parse a prediction tensor.

    This function is called internally (the user only needs to call `parse_prediction_tensor`).

    `parse_prediction_tensor` takes the outputs of this function (a bunch of numpy arrays, representing
    rows of the final parsed predictions tensor), and stacks them using `np.vstack`.

    The reason this function has been separated is because as of when I'm writing this,
    numba does not support np.vstack with arguments of different shapes/types. All
    the returned numpy arrays are single rows _except_ for `all_confs`, which has NUM_CLASSES rows.

    Parameters
    ----------
    prediction_tensor: np.ndarray
        The direct output tensor from a call to the YOGO model (1 * (5+NUM_CLASSES) * (Sx*Sy))
    img_h: int
    img_w: int

    Returns
    -------
    npt.NDArray: img_ids (1 x N)
    npt.NDArray: tlx (1 x N)
    npt.NDArray: tly (1 x N)
    npt.NDArray: brx (1 x N)
    npt.NDArray: bry (1 x N)
    npt.NDArray: objectness (1 x N)
    npt.NDArray: pred_labels (1 x N)
    npt.NDArray: peak pred_probs (1 x N)
    npt.NDArray: pred_probs (NUM_CLASSES x N)
    """

    mask = (prediction_tensor[:, 4:5, :] > 0.5).flatten()
    filtered_pred = prediction_tensor[:, :, mask][0, :, :]

    # Mask areas
    pred_half_width = filtered_pred[2] / 2 * img_w
    pred_half_height = filtered_pred[3] / 2 * YOGO_CROP_HEIGHT_PX
    areas = 4 * (pred_half_height * pred_half_width)
    area_mask = areas > YOGO_AREA_FILTER

    # Get coordinates
    filtered_pred = filtered_pred[:, area_mask]
    xc = filtered_pred[0, :] * img_w
    yc = filtered_pred[1, :] * img_h
    pred_half_width = filtered_pred[2] / 2 * img_w
    pred_half_height = filtered_pred[3] / 2 * img_h

    tlx = np.clip(np.rint(xc - pred_half_width).astype(DTYPE), 0, img_w)
    tly = np.clip(np.rint(yc - pred_half_height).astype(DTYPE), 0, img_h)
    brx = np.clip(np.rint(xc + pred_half_width).astype(DTYPE), 0, img_w)
    bry = np.clip(np.rint(yc + pred_half_height).astype(DTYPE), 0, img_h)

    objectness = filtered_pred[4, :].astype(DTYPE)
    all_confs = filtered_pred[5:, :].astype(DTYPE)
    pred_labels = np.argmax(all_confs, axis=0).astype(np.uint8)

    # Get peak prediction probabilities
    # Manually looping through because numba only supports
    # one advanced indexing operation at a time
    # (
    # otherwise we could do
    #   pred_probs = filtered_pred[5:, ]
    #      [
    #           pred_labels, np.arange(filtered_preds.shape[1])]
    #      ]
    # )
    s = int(filtered_pred.shape[1])
    pred_probs = np.zeros(s)
    for i in range(s):
        label = pred_labels[i]
        pred_probs[i] = all_confs[label, i]

    pred_labels = pred_labels.astype(DTYPE)
    pred_probs = pred_probs.astype(DTYPE)

    img_ids = np.ones(filtered_pred.shape[1]).astype(DTYPE) * img_id

    return img_ids, tlx, tly, brx, bry, objectness, pred_labels, pred_probs, all_confs


def parse_prediction_tensor(
    img_id: int,
    prediction_tensor: np.ndarray,
    img_h: int = DEFAULT_H,
    img_w: int = DEFAULT_W,
) -> npt.NDArray:
    """
    Parameters
    ----------
    prediction_tensor: np.ndarray
        The direct output tensor from a call to the YOGO model (1 * (5+NUM_CLASSES) * (Sx*Sy))
    img_h: int
    img_w: int

    Returns
    -------
    np.ndarray (dtype=DTYPE)
        A (8+NUM_CLASSES) x N array representing...

        idx 0 (img id)
        idx 1 - 4 (bounding boxes):
            top left x,
            top left y,
            bottom right x,
            bottom right y
        idx 5 (objectness)
            [0 - 1]
        idx 6 (predictions)
            Class id with the highest confidence value, number from 0 to M, where M is the number of classes - 1)
        idx 7 (peak prediction confidence)
            The highest predicted confidence value (yes, this is technically redundant so you could get the argmax from idxs 8-NUM_CLASSES, but this makes life more convenient for later analysis.)
        idx (8 - NUM_CLASSES)
            All the confidence values (the peak prediction confidence is repeated) for each class
    """

    prediction_tensor = prediction_tensor.astype(np.float32)
    return np.vstack(_parse_prediction_tensor(img_id, prediction_tensor, img_h, img_w))


def _write_thumbnail_from_pred_tensor(
    zarr_store: zarr.core.Array,
    preds: np.ndarray,
    idx: int,
    save_dir: Path,
):
    img_id = int(preds[0, idx])
    class_id = int(preds[6, idx])
    img_crop = _get_img_crop(zarr_store, preds[:, idx])
    conf = f"{preds[7, idx]:.5f}"
    filename = f"{idx:04}_class_{class_id:02}_frame_{img_id:05}_conf_{conf}.png"
    save_loc = str(save_dir / filename)

    cv2.imwrite(save_loc, img_crop)


def get_specific_class_from_parsed_tensor(
    parsed_prediction_tensor: npt.NDArray, class_id: int
) -> npt.NDArray:
    """Return all matches for the specific class ID in the parsed tensor.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray
        (8+NUM_CLASSES) x N array
    class_id: int

    Returns
    -------
    np.ndarray
        Shape: 8+NUM_CLASSES x N (N matches).
        Each column (i.e arr[:, i] is one predicted object).

        The 8 is the same dimension as the original prediction tensor, i.e:
            0 - img id
            1 - bounding box top left x
            2 - bounding box top left y
            3 - bounding box bottom right x
            4 - bounding box bottom right y
            5 - objectness (0 - 1)
            6 - class ID (all columns will have the same class ID as the one you passed into this function)
            7 - peak probability / confidence (0 - 1)
            8 - NUM_CLASSES

    """

    mask = parsed_prediction_tensor[6, :] == class_id
    return parsed_prediction_tensor[:, mask]


def _get_img_crop(
    zarr_store: zarr.core.Array, prediction_col: npt.NDArray
) -> npt.NDArray:
    img_id = prediction_col[0].astype(np.uint32)
    tlx, tly, brx, bry = prediction_col[1:5].astype(np.uint32)

    return YOGO.crop_img(zarr_store[:, :, img_id])[tly:bry, tlx:brx]


def _save_thumbnails_to_disk(
    zarr_store: zarr.core.Array,
    preds: npt.NDArray,
    save_dir: Path,
):
    """Save all the predictions in the given prediction tensor to the disk.

    Filenames have the following format:

    {number}_class_{class_number}_frame_{frame_id}_conf_{conf value}.png

    Parameters
    ----------
    zarr_store: zarr.core.Array
        Storage containing the images
    parsed_prediction_tensor: npt.NDArray
        Array of (5 + NUM_CLASSES) * N predictions
    save_dir: Path
        Where to save the thumbnails
    text: str
    """

    for i in range(preds.shape[1]):
        _write_thumbnail_from_pred_tensor(zarr_store, preds, i, save_dir)


def save_thumbnails_to_disk(
    zarr_store: zarr.core.Array,
    parsed_prediction_tensor: npt.NDArray,
    dataset_dir: Path,
    desired_class_ids: List[int] = CLASS_IDS_FOR_THUMBNAILS,
) -> Dict[str, Path]:
    """Save thumbnails to disk

    Parameters
    ----------
    zarr_store: zarr.core.Array
        Where the images are stored
    parsed_prediction_tensor: npt.NDArray
    dataset_dir: Path
        Where the experiment is stored (sets where the thumbnails folders will be saved)
    desired_class_ids: List[int]
        List of class IDs that should be saved, only these classes' thumbnails will be saved

    Returns
    -------
    Dict[str, Path]
        Mapping of class name to where its thumbnails are saved, e.g "Ring: "/example/thumbnails/rings". The caller should
        then call `os.listdir()` or something similar to get the list of all files within that folder.
    """

    # Create folders for thumbnails
    yogo_id_to_str = {v: k for k, v in YOGO_CLASS_IDX_MAP.items()}
    thumbnail_path = dataset_dir / "thumbnails"
    Path.mkdir(thumbnail_path, exist_ok=True)
    class_name_to_path = {
        yogo_id_to_str[x]: thumbnail_path / yogo_id_to_str[x] for x in desired_class_ids
    }
    for path in class_name_to_path.values():
        Path.mkdir(path, exist_ok=True)

    class_tensors = [
        get_specific_class_from_parsed_tensor(parsed_prediction_tensor, x)
        for x in desired_class_ids
    ]

    parasite_tensors_and_save_paths = zip(class_tensors, class_name_to_path.values())

    for class_tensor, path in parasite_tensors_and_save_paths:
        # Sort by descending confidence
        sort_by_confs = class_tensor[7, :].argsort()
        descending_confs = class_tensor[:, sort_by_confs][:, ::-1]

        # Limit the number of thumbnails saved for each class
        descending_confs_trunc = descending_confs[:, :MAX_THUMBNAILS_SAVED_PER_CLASS]
        _save_thumbnails_to_disk(zarr_store, descending_confs_trunc, path)

    return class_name_to_path


def scale_bbox_vals(
    parsed_prediction_tensor: npt.NDArray, scale_h: float, scale_w: float
) -> None:
    """Scale the bounding box locations by the given scale factors.
    NOTE: this modifies the array existing array!

    Parameters
    ----------
    parsed_prediction_tensor: np.ndarray (8+NUM_CLASSES x N)
    scale_h: float
    scale_w: float

    Returns
    -------
    np.ndarray
        8+NUM_CLASSES x N array with the indices [0-3] (corresponding to the bounding box corners) scaled by the given scale factors.
    """

    parsed_prediction_tensor[1, :] = np.rint(parsed_prediction_tensor[1, :] * scale_w)
    parsed_prediction_tensor[2, :] = np.rint(parsed_prediction_tensor[2, :] * scale_h)
    parsed_prediction_tensor[3, :] = np.rint(parsed_prediction_tensor[3, :] * scale_w)
    parsed_prediction_tensor[4, :] = np.rint(parsed_prediction_tensor[4, :] * scale_h)


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
        8+NUM_CLASSES x N array
    class_id: int
    confidence_threshold: float [0 - 1]

    Returns
    -------
    List[int]
        List of column IDs of the original parsed_prediction_tensor which have the
        matching class_id and confidence threshold greater than or equal to the one
        passed in.
    """

    mask = np.logical_and(
        parsed_prediction_tensor[6, :] == class_id,
        parsed_prediction_tensor[7, :] >= confidence_threshold,
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
        8+NUM_CLASSES x N array
    class_id: int
    confidence_threshold: float [0 - 1]

    Returns
    -------
    List[int]
        List of column IDs of the original parsed_prediction_tensor which have the
        matching class_id and confidence threshold less than or equal to the one
        passed in.
    """

    mask = np.logical_and(
        parsed_prediction_tensor[6, :] == class_id,
        parsed_prediction_tensor[7, :] <= confidence_threshold,
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
        8+NUM_CLASSES x N array
    confidence_threshold: DTYPE

    Returns
    -------
    np.ndarray
        8+NUM_CLASSES x M (M <= N)
    """

    mask = parsed_prediction_tensor[7, :] > confidence_threshold
    return parsed_prediction_tensor[:, mask]


def get_vals_less_than_conf_thresh(
    parsed_prediction_tensor: npt.NDArray, confidence_threshold: DTYPE
) -> npt.NDArray:
    """Given a prediction tensor, return all the columns which have a class prediction
    probability/confidence strictly less than the given threshold.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray
        8+NUM_CLASSES x N array
    confidence_threshold: float [0 - 1]

    Returns
    -------
    np.ndarray
        8+NUM_CLASSES x M (M <= N)
    """

    mask = parsed_prediction_tensor[7, :] < confidence_threshold
    return parsed_prediction_tensor[:, mask]


def get_individual_prediction_objs_from_parsed_tensor(
    parsed_prediction_tensor: npt.NDArray,
    col_idxs: Tuple[npt.NDArray],
    flip_conf_sign: bool = False,
) -> List[SinglePredictedObject]:
    """Get a list of individual prediction objects given a prediction tensor and
    a list of specified columns.

    Each SinglePredictedObject has a row of details about that predicted object
    0 - img_id
    1 - 4 bounding box
    5 - objectness
    6 - predicted class id
    7 - predicted class confidence
    8 - 8+NUM_CLASSES - all confidences (including the peak predicted)

    (8+NUM_CLASSES x 1 array)

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray (8+NUM_CLASSES x N) (where N is the number of objects detected for a particular image)
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
            parsed_prediction_tensor[:, i],
            conf=parsed_prediction_tensor[7, i] * flip,
        )
        for i in col_idxs
    ]


def get_all_argmax_confs_for_specific_class(
    class_id: int, prediction_tensor: npt.NDArray
) -> npt.NDArray:
    """
    Get all the confidence values associated with a particular class id that was predicted.

    Parameters
    ----------
    prediction_tensor: npt.NDArray (8+NUM_CLASSES x N)
        Array containing all the predictions (note filter out for non-zero predictions first)
        since the array is preallocated to (8+NUM_CLASSES x SOME_MAX_NUM).

    Returns
    -------
    np.ndarray
        1 x N where N is however many instances of that class were predicted
    """

    return prediction_tensor[7, prediction_tensor[6, :] == class_id]


def get_all_argmax_class_confidences_for_all_classes(
    prediction_tensor: npt.NDArray, num_classes: int = NUM_CLASSES
) -> List[npt.NDArray]:
    """Get all the confidences for each predicted class.

    Parameters
    ----------
    prediction_tensor: npt.NDArray
        Array containing all the predictions (note filter out for non-zero predictions first)
        since the array is preallocated to (8+NUM_CLASSES x SOME_MAX_NUM).

    Returns
    -------
    List[npt.NDArray]
        The index in the list corresponds to the numpy array of all confidences for that class.
    """

    return [
        get_all_argmax_confs_for_specific_class(id, prediction_tensor)
        for id in range(num_classes)
    ]


def get_all_confs_for_specific_class(
    class_id: int, prediction_tensor: npt.NDArray
) -> npt.NDArray:
    """Get all the confidence values for a given class
    (i.e this includes confidences of predictions where that class wasn't the predicted one!)

    Potentially useful for getting counts based on expectation value?

    Parameters
    ----------
    prediction_tensor: npt.NDArray
        Array containing all the predictions (note filter out for non-zero predictions first)
        since the array is preallocated to (8+NUM_CLASSES x SOME_MAX_NUM).

    Returns
    -------
    np.ndarray (1 x N)
    """

    return prediction_tensor[8 + class_id, :]


def get_all_confs_for_all_classes(
    prediction_tensor: npt.NDArray, num_classes: int = NUM_CLASSES
) -> List[npt.NDArray]:
    """Get all the confidences for each class (includes confidences that are not the argmax
    confidence for that particular prediction!).

    Each index of the returned list corresponds to a particular class.

    Parameters
    ----------
    prediction_tensor: npt.NDArray
        Array containing all the predictions (note filter out for non-zero predictions first)
        since the array is preallocated to (8+NUM_CLASSES x SOME_MAX_NUM).

    Returns
    -------
    List[np.ndarray]
        len=NUM_CLASSES
        np.ndarray (1xN)
    """
    return [
        get_all_confs_for_specific_class(i, prediction_tensor)
        for i in range(num_classes)
    ]


def get_class_counts(
    prediction_tensor: npt.NDArray,
    num_classes: int = NUM_CLASSES,
    conf_thresh: float = YOGO_CONF_THRESHOLD,
) -> List[int]:
    """Get the number of occurrences for each class.

    Parameters
    ----------
    prediction_tensor: npt.NDArray
        Array containing all the predictions (note filter out for non-zero predictions first)
        since the array is preallocated to (8+NUM_CLASSES x SOME_MAX_NUM).
    num_classes: int
        Defaults to NUM_CLASSES
    conf_thresh: float
        Defaults to YOGO_CONF_THRESHOLD

    Returns
    -------
    List[int]
        The index in the list corresponds to the class id (i.e output[0] would have the counts for all the healthy cells)
    """

    conf_filtered = prediction_tensor[:, prediction_tensor[7, :] > conf_thresh]
    ids, counts = np.unique(conf_filtered[6, :], return_counts=True)
    id_and_counts = dict(zip(ids, counts))
    return [id_and_counts.get(i, 0) for i in range(num_classes)]


@njit(cache=True)
def nms(parsed_prediction_tensor: npt.NDArray, thresh: float) -> List[int]:
    """
    Fast R-CNN
    Copyright (c) 2015 Microsoft
    Licensed under The MIT License [see LICENSE for details]
    Written by Ross Girshick
    --------------------------------------------------------

    Uses a greedy algorithm to determine which bboxes to keep.

    Parameters
    ----------
    parsed_prediction_tensor: npt.NDArray (8+NUM_CLASSES) x N
        Prediction tensor for a single image
    thresh: float
        Intersection-over-union threshold for removal

    Returns
    -------
    List[int]
        Indices of which predictions to keep
    """
    x1 = parsed_prediction_tensor[1, :]
    y1 = parsed_prediction_tensor[2, :]
    x2 = parsed_prediction_tensor[3, :]
    y2 = parsed_prediction_tensor[4, :]

    areas = (x2 - x1 + 1) * (y2 - y1 + 1)

    confs: npt.NDArray = parsed_prediction_tensor[8, :]
    order = confs.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]  # pick maxmum iou box
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1 + 1)  # maximum width
        h = np.maximum(0.0, yy2 - yy1 + 1)  # maxiumum height
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(ovr <= thresh)[0]
        order = order[inds + 1]

    return keep
