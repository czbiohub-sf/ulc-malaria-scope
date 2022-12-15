#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel
from ulc_mm_package.neural_nets.neural_network_constants import AUTOFOCUS_MODEL_DIR
from ulc_mm_package.hardware.camera import Camera


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
        super().__init__(model_path=model_path)

    def __call__(self, input_img):
        return self.syn(input_img)
