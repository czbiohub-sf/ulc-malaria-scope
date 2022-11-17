#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.neural_network_constants import (
    YOGO_MODEL_DIR,
    YOGO_PRED_THRESHOLD,
)


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
        super().__init__(model_path)

    def __call__(self, input_img, idxs=None):
        return self.asyn(input_img, idxs)

    def syn(self, input_img):
        res = super().syn(input_img)
        return self.filter_res(res)

    def filter_res(self, res):
        if res.ndim == 4:
            bs, pred_dim, Sy, Sx = res.shape
            # constant time op, just changes view of res
            res.shape = (bs, pred_dim, Sy * Sx)
        mask = (res[:, 4:5, :] > YOGO_PRED_THRESHOLD).flatten()
        return res[:, :, mask]

    def _default_callback(self, infer_request, userdata):
        self._asyn_results.append(
            (userdata, self.filter_res(infer_request.output_tensors[0].data))
        )


if __name__ == "__main__":
    import cv2
    import sys
    import numpy as np
    import time

    Y = YOGO()
    img = cv2.imread(sys.argv[1], cv2.IMREAD_GRAYSCALE)

    Y([img, img])
    time.sleep(1)
    res = Y.get_asyn_results()
    print(res)
