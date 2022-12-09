#! /usr/bin/env python3

import sys
import time
import threading
import numpy as np
import operator as op
import numpy.typing as npt

from copy import copy
from contextlib import contextmanager
from concurrent.futures import Future, ThreadPoolExecutor

from functools import partial
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

from ulc_mm_package.utilities.lock_utils import lock_timeout
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

        # used for syn
        self._temp_infer_queue = AsyncInferQueue(self.model)

        # used for asyn
        self.asyn_infer_queue = AsyncInferQueue(self.model)
        self.asyn_infer_queue.set_callback(self._default_callback)
        self._asyn_results: List[AsyncInferenceResult] = []

        self._executor = ThreadPoolExecutor(max_workers=1)
        self._futures: List[Future] = []

    def _compile_model(
        self,
        model_path: str,
        camera_selection: CameraOptions,
    ):
        if self.connected:
            raise RuntimeError(f"model {self} already compiled")

        # when the first subclass is initialized, core will be given a value
        assert (
            self.core is not None
        ), "initialize a subclass of NCSModel, not NCSModel itself"

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
                        f"Failed to connect NCS: {e}.\nRemaining connection "
                        f"attempts: {4 - connection_attempts}. Retrying..."
                    )
                err_msg = str(e)
        raise TPUError(f"Failed to connect to NCS: {err_msg}")

    def syn(
        self, input_imgs: Union[npt.NDArray, List[npt.NDArray]], sort: bool = False
    ) -> List[npt.NDArray]:
        """'Synchronously' infers images on the NCS

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
            return [r.result for r in sorted(res, key=op.attrgetter("id"))]
        return [r.result for r in res]

    def asyn(
        self,
        input_img: npt.NDArray,
        id: Optional[int] = None,
    ) -> None:
        """Asynchronously submits inference jobs to the NCS

        params:
            input_imgs: the image/images to be inferred.
            ids: the ids that are passed through the asynchronous inference,
                 used for associating the predicted tensor with the input image.

        To get results, call 'get_asyn_results'
        """
        input_tensor = self._format_image_to_tensor(input_img)
        self._futures.append(
            self._executor.submit(
                self.asyn_infer_queue.start_async,
                args=({0: input_tensor},),
                kwargs={"userdata": id},
            )
        )

    def get_asyn_results(
        self, timeout: Optional[float] = 0.01
    ) -> Optional[List[AsyncInferenceResult]]:
        """
        Maybe return some asyn_results. Will return None if it can not get the lock
        on results within `timeout`. To disable timeout (i.e. just block indefinitely),
        set timeout to None
        """
        # openvino sets timeout to indefinite on timeout < 0, not timeout == None
        if timeout is None:
            timeout = -1

        self._futures = [f for f in self._futures if not f.done()]

        with lock_timeout(self.lock, timeout=timeout):
            res = copy(self._asyn_results)
            self._asyn_results = []
            return res

    def wait_all(self):
        """wait for all pending InferRequests to resolve"""
        self.asyn_infer_queue.wait_all()

    def _default_callback(self, infer_request: InferRequest, userdata: Any) -> None:
        with lock_timeout(self.lock):
            self._asyn_results.append(
                AsyncInferenceResult(
                    id=userdata, result=infer_request.output_tensors[0].data[:]
                )
            )

    def _cb(
        self, result_list: List, infer_request: InferRequest, userdata: Any
    ) -> None:
        result_list.append(
            AsyncInferenceResult(
                id=userdata, result=infer_request.output_tensors[0].data[:]
            )
        )

    def _as_sequence(self, maybe_list: Union[T, List[T]]) -> Sequence[T]:
        if isinstance(maybe_list, Sequence):
            return maybe_list
        return [maybe_list]

    def _format_image_to_tensor(self, img: npt.NDArray) -> List[Tensor]:
        return Tensor(np.expand_dims(img, (0, 3)), shared_memory=False)

    def shutdown(self):
        self._executor.shutdown(wait=True)
