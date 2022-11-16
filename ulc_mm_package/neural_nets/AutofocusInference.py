#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.neural_net_constants import AUTOFOCUS_MODEL_DIR
from ulc_mm_package.scope_constants import CameraOptions, CAMERA_SELECTION


class AutoFocus(NCSModel):
    """
    Autofocus Model

    Usage:
        >>> A = AutoFocus("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        >>> A(img)
        <steps from 0!>
    """

    def __init__(
        self,
        model_path: str = AUTOFOCUS_MODEL_DIR,
        camera_selection: CameraOptions = CAMERA_SELECTION,
    ):
        super().__init__(
            model_path=model_path,
            optimization_hint=OptimizationHint.LATENCY,
            camera_selection=camera_selection,
        )

    def __call__(self, input_img):
        return self.syn(input_img)[0][0]


def pre_process_image(image_path):
    image = Image.open(image_path).convert("L")
    image = image.resize((300, 400), resample=Image.BILINEAR)
    return np.array(image).astype(np.float16)


def read_grayscale(path):
    im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(im, (400, 300))


if __name__ == "__main__":
    import os
    import cv2
    import sys
    import numpy as np
    import time
    from pathlib import Path
    import matplotlib.pyplot as plt
    from ulc_mm_package.scope_constants import CameraOptions
    from PIL import Image

    ex = cv2.imread(str(next(Path(sys.argv[1]).glob("*.png"))), cv2.IMREAD_GRAYSCALE)

    if ex.shape == (600, 800):
        A = AutoFocus(camera_selection=CameraOptions.BASLER)
    else:
        A = AutoFocus(camera_selection=CameraOptions.AVT)

    for imgpath in sorted(Path(sys.argv[1]).glob("*.png")):
        # im = read_grayscale(imgpath)
        im = cv2.imread(str(imgpath), cv2.IMREAD_GRAYSCALE)  # .astype(np.float16)
        # im = pre_process_image(str(imgpath))
        print(A(im))

    sys.exit(0)
