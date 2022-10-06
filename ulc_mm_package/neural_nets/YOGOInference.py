#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.yogo_constants import YOGO_MODEL_DIR, YOGO_PRED_THRESHOLD


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

    def __init__(self, model_path: str = YOGO_MODEL_DIR):
        super().__init__(model_path, OptimizationHint.THROUGHPUT)

    def __call__(self, input_img):
        return self.asyn(input_img)

    def syn(self, input_img):
        res = super().syn(input_img)
        return self.filter_res(res)

    def filter_res(self, res):
        "filter results"
        # if we call this multiple times on res, we gotta do this
        if res.ndim == 4:
            bs, pred_dim, Sy, Sx = res.shape
            # constant time op, just changes view of res
            res.shape = (bs, pred_dim, Sy * Sx)
        mask = (res[:, 4:5, :] > YOGO_PRED_THRESHOLD).flatten()
        return res[:,:,mask]


if __name__ == "__main__":
    import cv2
    import sys
    import numpy as np

    Y = YOGO()
    img = cv2.imread(sys.argv[1], cv2.IMREAD_GRAYSCALE)
    imgg = np.concatenate((img,img,img,img))
    print(imgg.shape)

    vv = Y.syn(imgg)[0]

    for row in vv[0,...].T:
        print(row.shape, row)
