#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.neural_net_constants import AUTOFOCUS_MODEL_DIR


class AutoFocus(NCSModel):
    """
    Autofocus Model

    Usage:
        >>> A = AutoFocus("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        >>> A(img)
        <steps from 0!>
    """

    def __init__(self, model_path: str = AUTOFOCUS_MODEL_DIR):
        super().__init__(model_path, OptimizationHint.LATENCY)

    def __call__(self, input_img):
        return self.syn(input_img)[0][0]


if __name__ == "__main__":
    import os
    import cv2
    import sys
    import numpy as np
    import time
    from pathlib import Path
    import matplotlib.pyplot as plt

    A = AutoFocus()

    for imgpath in Path(sys.argv[1]).glob("*.png"):
        im = cv2.imread(str(imgpath), cv2.IMREAD_GRAYSCALE).astype(np.float16)
        print(A(im))
