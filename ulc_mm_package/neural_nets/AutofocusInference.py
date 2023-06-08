#! /usr/bin/env python3

import queue

from ulc_mm_package.neural_nets.NCSModel import NCSModel
from ulc_mm_package.neural_nets.neural_network_constants import (
    AUTOFOCUS_MODEL_DIR,
    AF_QSIZE,
)
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
            camera_selection=camera_selection,
        )

        # Bypass mypy because it dislikes changing the queue type
        self._executor._work_queue = queue.Queue(maxsize=AF_QSIZE)  # type:ignore

    def __call__(self, input_img):
        return self.syn(input_img)
