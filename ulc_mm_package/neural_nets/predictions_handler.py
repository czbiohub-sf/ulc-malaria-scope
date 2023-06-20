import heapq as hq
from typing import Dict, List, NamedTuple

import numpy.typing as npt
import zarr

import ulc_mm_package.neural_nets.utils as nn_utils
from ulc_mm_package.neural_nets.NCSModel import AsyncInferenceResult
from ulc_mm_package.scope_constants import CAMERA_SELECTION, MAX_FRAMES, MAX_THUMBNAILS
from ulc_mm_package.neural_nets.neural_network_constants import (
    IMG_RESIZED_DIMS,
    YOGO_CLASS_LIST,
    YOGO_CLASS_IDX_MAP,
)

IMG_W, IMG_H = CAMERA_SELECTION.IMG_WIDTH, CAMERA_SELECTION.IMG_HEIGHT
RESIZED_W, RESIZED_H = IMG_RESIZED_DIMS
SCALE_H, SCALE_W = IMG_W / RESIZED_W, IMG_H / RESIZED_H
UINT16_MAX = 65535


class Thumbnail(NamedTuple):
    img_crop: npt.NDArray  # n x m array (different for every thumbnail)
    confidence: float  # value between [0-1]


class PredictionsHandler:
    """A class to store and handle prediction tensors
    from YOGO.

    Handle:
    1. Parsing prediction tensors into a more ergonomic format
    2. Storing the prediction tensors from each image in memory
    3. Extracting min/max confidence predictions for each class for a given image's prediction tensor
    4. Determining if there are stuck cells/debris that persist over many frames
    """

    def __init__(self):
        self.pred_tensors = [None] * MAX_FRAMES

        class_ids = [YOGO_CLASS_IDX_MAP[x] for x in YOGO_CLASS_LIST]
        self.class_ids = class_ids

        self.max_confs: Dict[int, List[nn_utils.SinglePredictedObject]] = {
            x: [] for x in class_ids
        }
        self.curr_min_of_max_confs_by_class = {x: 0 for x in class_ids}

        self.min_confs: Dict[int, List[nn_utils.SinglePredictedObject]] = {
            x: [] for x in class_ids
        }
        self.curr_max_of_min_confs_by_class = {x: UINT16_MAX for x in class_ids}

    def add_yogo_pred(self, res: AsyncInferenceResult) -> None:
        """Store the parsed YOGO prediction tensor and update the min/max confidence objects for each class.

        Parameters
        ----------
        res: AsyncInferenceResult
        """

        img_id = int(res.id)
        pred_tensor = res.result

        # Parse tensor to 7 x N format (N predictions)
        parsed_tensor = nn_utils.parse_prediction_tensor(
            pred_tensor, img_h=RESIZED_H, img_w=RESIZED_W
        )

        # Scale the bounding box locations so they can be used with
        # the original sized images
        nn_utils.scale_bbox_vals(parsed_tensor, SCALE_H, SCALE_W)
        self.pred_tensors[img_id] = parsed_tensor

        for x in self.class_ids:
            max_conf_col_ids = (
                nn_utils.get_col_ids_for_matching_class_and_above_conf_thresh(
                    parsed_tensor, x, self.curr_min_of_max_confs_by_class[x]
                )
            )

            # Pair up the confidences and column ids and sort them by confidences
            # and keep only the MAX_THUMBNAILS highest
            if len(max_conf_col_ids[0] > 0):
                _, max_conf_col_ids = zip(
                    *list(
                        sorted(
                            zip(
                                list(parsed_tensor[6, max_conf_col_ids][0]),
                                list(max_conf_col_ids[0]),
                            ),
                            key=lambda y: y[0],
                        )
                    )[-MAX_THUMBNAILS:]
                )

                [
                    hq.heappushpop(self.max_confs[x], i)  # type: ignore
                    if len(self.max_confs[x]) > MAX_THUMBNAILS
                    else hq.heappush(self.max_confs[x], i)  # type: ignore
                    for i in nn_utils.get_individual_prediction_objs_from_parsed_tensor(
                        img_id, parsed_tensor, max_conf_col_ids
                    )
                ]
                lowest_max_conf = self.max_confs[x][0].conf
                self.curr_min_of_max_confs_by_class[x] = lowest_max_conf

                # This is for the very first iteration so that we don't get
                # duplicate entries in both the max conf and min conf lists
                if self.curr_max_of_min_confs_by_class[x] == UINT16_MAX:
                    self.curr_max_of_min_confs_by_class[x] = lowest_max_conf

            # Repeat the above for minimum confidences
            min_conf_col_ids = (
                nn_utils.get_col_ids_for_matching_class_and_below_conf_thresh(
                    parsed_tensor, x, self.curr_max_of_min_confs_by_class[x]
                )
            )
            if len(min_conf_col_ids[0] > 0):
                _, min_conf_col_ids = zip(
                    *list(
                        sorted(
                            zip(
                                list(parsed_tensor[6, min_conf_col_ids][0]),
                                list(min_conf_col_ids[0]),
                            ),
                            key=lambda y: y[0],
                        )
                    )[:MAX_THUMBNAILS]
                )

                [
                    hq.heappushpop(self.min_confs[x], i)  # type: ignore
                    if len(self.max_confs[x]) > MAX_THUMBNAILS
                    else hq.heappush(self.min_confs[x], i)  # type: ignore
                    for i in nn_utils.get_individual_prediction_objs_from_parsed_tensor(
                        img_id, parsed_tensor, min_conf_col_ids, flip_conf_sign=True
                    )
                ]
                highest_min_conf = self.min_confs[x][0].conf
                self.curr_max_of_min_confs_by_class[x] = highest_min_conf

    def _get_thumbnails(
        self,
        zarr_store: zarr.core.Array,
        confs: Dict[int, List[nn_utils.SinglePredictedObject]],
    ) -> Dict[int, List[Thumbnail]]:
        """Extract thumbnails from the specified confidence Dict (i.e self.min_confs or self.max_confs)

        Parameters
        ----------
        zarr_store: zarr.core.Array
            Zarr store in which the original images are stored
        confs: Dict[int, List[nn_utils.SinglePredictedObject]]
            Either self.min_confs or self.max_confs

        Returns
        -------
        Dict[int, List[npt.NDArray]]
            int (class_id) -> List of thumbnails (numpy arrays)
        """

        thumbnails: Dict[int, List[npt.NDArray]] = {x: [] for x in self.class_ids}
        for c in self.class_ids:
            for obj in confs[c]:
                img_id = obj.img_id
                tlx, tly, brx, bry = obj.parsed[:4]
                img_crop = zarr_store[:, :, img_id][tly:bry, tlx:brx]
                thumbnails[c].append(
                    Thumbnail(
                        img_crop=img_crop,
                        confidence=obj.parsed[6],
                    )
                )

        return thumbnails

    def get_max_conf_thumbnails(
        self, zarr_store: zarr.core.Array
    ) -> Dict[int, List[Thumbnail]]:
        """Get the maximum confidence thumbnails.

        Parameters
        ----------
        zarr_store: zarr.core.Array
            Zarr store in which the original images are stored

        Returns
        -------
        Dict[int, List[npt.NDArray]]
            int (class_id) -> List of thumbnails (numpy arrays)
        """

        return self._get_thumbnails(zarr_store, self.max_confs)

    def get_min_conf_thumbnails(
        self, zarr_store: zarr.core.Array
    ) -> Dict[int, List[Thumbnail]]:
        """Get the minimum confidence thumbnails.

        Parameters
        ----------
        zarr_store: zarr.core.Array
            Zarr store in which the original images are stored

        Returns
        -------
        Dict[int, List[npt.NDArray]]
            int (class_id) -> List of thumbnails (numpy arrays)
        """

        return self._get_thumbnails(zarr_store, self.min_confs)

    def get_prediction_tensors(self) -> List[npt.NDArray]:
        return self.pred_tensors
