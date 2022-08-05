#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint


class AutoFocus(NCSModel):
    """
    Autofocus Model

    Usage:
        >>> A = AutoFocus("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        >>> A(img)
        <steps from 0!>
    """

    def __init__(self, model_path: str):
        super().__init__(model_path, OptimizationHint.LATENCY)

    def __call__(self, input_img):
        return self.syn(input_img)
