#! /usr/bin/env python3

import numpy as np
import numpy.typing as npt

from ulc_mm_package.neural_nets.NCSModel import NCSModel
from ulc_mm_package.neural_nets.neural_network_constants import (
    QC_MODEL_DIR,
    QC_CACHE_DIR,
)


class QC(NCSModel):
    """
    QC model (resnet18)
    """

    def __init__(
        self,
        model_path: str = QC_MODEL_DIR,
        cache_dir: str = QC_CACHE_DIR,
    ):
        super().__init__(model_path=model_path, cache_dir=cache_dir)

    def _format_image_to_tensor(self, img: npt.NDArray) -> npt.NDArray:
        # Single-channel image to 3-channel
        img = np.stack((img,) * 3, axis=0)

        # Add batch dimension
        img = np.expand_dims(img, axis=0)

        # Reshape to match model input dimensions
        img = np.reshape(img, (1, 3, 772, 1032))

        # Normalize pixel values to range [0, 1]
        img = np.array(img, dtype=np.float32)
        img = img / 255.0

        # Apply mean and standard deviation normalization
        means = np.array([0.485, 0.456, 0.406]).reshape(1, 3, 1, 1)
        sds = np.array([0.229, 0.224, 0.225]).reshape(1, 3, 1, 1)
        img = (img - means) / sds

        return img

    def _sigmoid(self, x: npt.NDArray) -> npt.NDArray:
        """
        Sigmoid function
        """
        return 1 / (1 + np.exp(-x))

    def __call__(self, input_img):
        return [self._sigmoid(x) for x in self.syn(input_img)]
