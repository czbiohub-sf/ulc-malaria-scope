#! /usr/bin/env python3


import numpy.typing as npt

from typing import List, Union


from ulc_mm_package.neural_nets.NCSModel import (
    NCSModel,
    AsyncInferenceResult,
    lock_timeout,
)
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_MODEL_DIR,
    YOGO_PRED_THRESHOLD,
)
from ulc_mm_package.scope_constants import CameraOptions, CAMERA_SELECTION


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
        <Bounding Boxes!>
    """

    def __init__(
        self,
        model_path: str = YOGO_MODEL_DIR,
        camera_selection: CameraOptions = CAMERA_SELECTION,
    ):
        super().__init__(model_path, camera_selection)

    @staticmethod
    def filter_res(res, threshold=YOGO_PRED_THRESHOLD):
        # TODO: make sure this is filtering correctly
        mask = (res[:, 4:5, :] > threshold).flatten()
        return res[:, :, mask]

    @staticmethod
    def _format_res(res):
        bs, pred_dim, Sy, Sx = res.shape
        res.shape = (bs, pred_dim, Sy * Sx)
        return res

    def __call__(self, input_img, idxs=None):
        return self.asyn(input_img, idxs)

    def syn(
        self, input_imgs: Union[npt.NDArray, List[npt.NDArray]], sort: bool = False
    ):
        return [YOGO._format_res(r) for r in super().syn(input_imgs, sort)]

    def _default_callback(self, infer_request, userdata):
        res = infer_request.output_tensors[0].data[:]
        res = YOGO._format_res(res)

        with lock_timeout(self.lock):
            self._asyn_results.append(AsyncInferenceResult(id=userdata, result=res))
