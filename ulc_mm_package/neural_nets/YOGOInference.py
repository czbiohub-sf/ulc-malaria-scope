#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.yogo_constants import YOGO_MODEL_DIR


class YOLO(NCSModel):
    """
    YOLO Model

    Usage:
        >>> Y = YOLO("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image)  # our YOLO takes grayscale only so far - I'll take care of it
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


if __name__ == "__main__":
    import cv2

    Y = YOLO("model.xml")
    img = cv2.imread()
