#! /usr/bin/env python3


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

    def __call__(self, input_img, idxs=None):
        return self.asyn(input_img, idxs)

    def _default_callback(self, infer_request, userdata):
        res = infer_request.output_tensors[0].data[:]
        bs, pred_dim, Sy, Sx = res.shape
        res.shape = (bs, pred_dim, Sy * Sx)

        with lock_timeout(self.lock):
            self._asyn_results.append(AsyncInferenceResult(id=userdata, result=res))
