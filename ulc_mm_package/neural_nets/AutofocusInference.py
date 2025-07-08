#! /usr/bin/env python3

from functools import partial
import queue
from typing import Any, Union, List

import numpy.typing as npt

from ulc_mm_package.neural_nets.NCSModel import (
    NCSModel,
    AsyncInferenceResult,
    InferRequest,
)
from ulc_mm_package.neural_nets.neural_network_constants import (
    AUTOFOCUS_MODEL_DIR,
    AUTOFOCUS_CACHE_DIR,
    AF_QSIZE,
    MODELS,
)
from ulc_mm_package.utilities.lock_utils import lock_timeout


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
        cache_dir: str = AUTOFOCUS_CACHE_DIR,
    ):
        super().__init__(
            model_path=model_path, model_type=MODELS.AUTOFOCUS, cache_dir=cache_dir
        )

        # Bypass mypy because it dislikes changing the queue type
        self._executor._work_queue = queue.Queue(maxsize=AF_QSIZE)  # type:ignore

    def __call__(self, input_img):
        return self.syn(input_img)

    def _cb(
        self, result_list: List, infer_request: InferRequest, userdata: Any
    ) -> None:
        result_list.append(
            [
                AsyncInferenceResult(
                    id=userdata, result=infer_request.output_tensors[0].data.copy()
                ),
                AsyncInferenceResult(
                    id=userdata, result=infer_request.output_tensors[1].data.copy()
                ),
            ]
        )

    def _default_callback(self, infer_request: InferRequest, userdata: Any) -> None:
        r = [
            AsyncInferenceResult(
                id=userdata, result=infer_request.output_tensors[0].data.copy()
            ),
            AsyncInferenceResult(
                id=userdata, result=infer_request.output_tensors[1].data.copy()
            ),
        ]
        with lock_timeout(self.asyn_result_lock):
            self._asyn_results.append(r)

    def syn(
        self, input_imgs: Union[npt.NDArray, List[npt.NDArray]], sort: bool = False
    ) -> List[npt.NDArray]:
        """'Synchronously' infers images on the NCS.

        The AutoFocus model returns two outputs:
            - A tensor of length three where the elements are logits which correspond to below/in-focus/above focus (indices 0, 1, 2 respectively).
            - A tensor of length ~20 whose logit indices correspond to the magnitude of the defocus (in steps) (i.e index 10 is a deblur of magnitude 10 steps away)

        Under the hood, it is asynchronous, because asynchronous performance matches synchronous
        or bests synchronous performance, even for n = 1.

        This is a "synchronous" function
        in the sense that it blocks. I.e. it blocks until it returns a result, as opposed to
        asynchronous inference which would immediately return.

        params:
            input_imgs: the image/images to be inferred.
            sort: sort the outputs
        """
        res: List[AsyncInferenceResult] = []

        self._temp_infer_queue.set_callback(partial(self._cb, res))

        for i, image in enumerate(self._as_sequence(input_imgs)):
            tensor = self._format_image_to_tensor(image)
            self._temp_infer_queue.start_async({0: tensor}, userdata=i)

        self._temp_infer_queue.wait_all()

        if sort:
            return [
                (r[0].result, r[1].result) for r in sorted(res, key=lambda x: x[0].id)
            ]
        return [(r[0].result, r[1].result) for r in res]
