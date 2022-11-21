#! /usr/bin/env python3

import sys
import time
import threading
import numpy as np
import numpy.typing as npt

from copy import copy
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

from collections import namedtuple
from typing import (
    Any,
    List,
    Sequence,
    Optional,
    Union,
    TypeVar,
    cast,
)

from ulc_mm_package.scope_constants import CameraOptions, CAMERA_SELECTION

from openvino.preprocess import PrePostProcessor, ResizeAlgorithm
from openvino.runtime import (
    Core,
    Layout,
    Type,
    InferRequest,
    AsyncInferQueue,
    Tensor,
)


T = TypeVar("T", covariant=True)


class TPUError(Exception):
    pass


@contextmanager
def lock_timeout(lock, timeout=-1):
    """lock context manager w/ timeout

    timeout value of -1 disables timeout
    """
    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        lock.release()


AsyncInferenceResult = namedtuple("AsyncInferenceResult", ["id", "result"])


class NCSModel:
    """
    Neural Compute Stick 2 Model

    Allows you to run a model (defined by an intel intermediate representation of your
    model, e.g. model.xml & model.bin) on the neural compute stick

    Best docs
    https://docs.openvino.ai/latest/api/ie_python_api/api.html
    https://docs.openvino.ai/latest/openvino_docs_OV_UG_Python_API_exclusives.html
    """

    core = None

    def __init_subclass__(cls, *args, **kwargs):
        if NCSModel.core is None:
            NCSModel.core = Core()
        cls.core = NCSModel.core

    def __init__(
        self,
        model_path: str,
        camera_selection: CameraOptions = CAMERA_SELECTION,
    ):
        """
        params:
            model_path: path to the 'xml' file
            camera_selection: the camera that is used for inference. Just used for img dims
        """
        self.lock = threading.Lock()
        self.connected = False
        self.device_name = "MYRIAD"
        self.model = self._compile_model(model_path, camera_selection)
        self.num_requests = self.model.get_property("OPTIMAL_NUMBER_OF_INFER_REQUESTS")

        self.asyn_infer_queue = AsyncInferQueue(self.model, jobs=self.num_requests)
        self.asyn_infer_queue.set_callback(self._default_callback)

        self._asyn_results: List[AsyncInferenceResult] = []

    def _compile_model(
        self,
        model_path: str,
        camera_selection: CameraOptions,
    ):
        if self.connected:
            raise RuntimeError(f"model {self} already compiled")

        # when the first subclass is initialized, core will be given a value
        assert self.core is not None, "initialize a subclass of NCSModel, not NCSModel itself"

        model = self.core.read_model(model_path)

        ppp = PrePostProcessor(model)
        # black likes to format this into a very unreadable format :(
        # fmt: off
        ppp.input() \
            .tensor() \
            .set_element_type(Type.u8) \
            .set_layout(Layout("NHWC")) \
            .set_spatial_static_shape(
                camera_selection.IMG_HEIGHT, camera_selection.IMG_WIDTH
            )
        # fmt: on
        ppp.input().preprocess().resize(ResizeAlgorithm.RESIZE_LINEAR)
        ppp.input().model().set_layout(Layout("NCHW"))
        ppp.output().tensor().set_element_type(Type.f32)
        model = ppp.build()

        err_msg = ""
        connection_attempts = 0
        while connection_attempts < 4:
            # sleep 0, then 1, then 3, then 7
            time.sleep(2**connection_attempts - 1)
            try:
                # TODO: benchmark_app.py says PERFORMANCE_HINT = 'none' w/ nstreams=1 is fastest!!
                compiled_model = self.core.compile_model(
                    model,
                    self.device_name,
                )
                self.connected = True
                return compiled_model
            except Exception as e:
                connection_attempts += 1
                if connection_attempts < 4:
                    print(
                        f"Failed to connect NCS: {e}.\nRemaining connection attempts: {4 - connection_attempts}. Retrying..."
                    )
                err_msg = str(e)
        raise TPUError(f"Failed to connect to NCS: {err_msg}")

    def syn(self, input_imgs: Union[npt.NDArray, List[npt.NDArray]]):
        """ Synchronously infers images on the NCS

        params:
            input_imgs: the image/images to be inferred.
        """
        input_imgs = self._as_list(input_imgs)
        input_tensors = self._format_images_to_tensors(input_imgs)
        output_layer = self.model.output(0)
        return self.model(input_tensors)[output_layer]

    def asyn(
        self,
        input_imgs: Union[npt.NDArray, List[npt.NDArray]],
        ids: Optional[Union[int, Sequence[int]]] = None,
    ) -> None:
        """ Asynchronously submits inference jobs to the NCS

        params:
            input_imgs: the image/images to be inferred.
            ids: the ids that are passed through the asynchronous inference,
                 used for associating the predicted tensor with the input image.

        To get results, call 'get_asyn_results'
        """
        input_imgs = self._as_list(input_imgs)

        if ids is None:
            ids = range(len(input_imgs))

        ids = self._as_list(ids)

        if len(ids) != len(input_imgs):
            raise ValueError(
                f"the number of ids must be the number of input images. "
                f"len(input_imgs) == {len(input_imgs)}, len(ids) == {len(ids)}"
            )

        input_tensors = self._format_images_to_tensors(input_imgs)
        self.asyn_infer_queue.start_async({0: input_tensors}, userdata=ids)

    def get_asyn_results(self, timeout=0.01) -> Optional[List[AsyncInferenceResult]]:
        """
        Maybe return some asyn_results. Will return None if it can not get the lock
        on results within `timeout`. To disable timeout (i.e. just block indefinitely),
        use a negative number for timeout.
        """
        with lock_timeout(self.lock, timeout=timeout):
            res = copy(self._asyn_results)
            self._asyn_results = []
            return res

    def wait_all(self):
        self.asyn_infer_queue.wait_all()

    def _default_callback(self, infer_request: InferRequest, userdata: Any) -> None:
        with lock_timeout(self.lock):
            self._asyn_results.append(
                AsyncInferenceResult(
                    id=userdata, result=infer_request.output_tensors[0].data
                )
            )

    def _as_list(self, val: Union[T, Sequence[T]]) -> List[T]:
        "returns val as a list; if it is already a list, leave it be"
        if not isinstance(val, Sequence):
            val = [val]
        return cast(list, val)

    def _format_images_to_tensors(self, imgs: List[npt.NDArray]) -> List[Tensor]:
        return [
            Tensor(np.expand_dims(img, (0, 3)), shared_memory=True)
            for img in imgs
        ]
