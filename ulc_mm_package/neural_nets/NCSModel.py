#! /usr/bin/env python3

import sys
import time
import threading
import numpy as np
import numpy.typing as npt

from PIL import Image
from enum import Enum
from pathlib import Path
from copy import copy
from contextlib import contextmanager

from collections import namedtuple
from typing import Any, Callable, List, Sequence, Optional, Tuple

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


class TPUError(Exception):
    pass


class OptimizationHint(Enum):
    LATENCY = 1
    THROUGHPUT = 2


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


AsyncInferenceResult = namedtuple("AsyncInferenceResult", ("id", "result"))


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
        """
        self.lock = threading.Lock()
        self.connected = False
        self.device_name = "MYRIAD"
        self.model = self._compile_model(model_path, camera_selection)
        self.num_requests = self.model.get_property("OPTIMAL_NUMBER_OF_INFER_REQUESTS")
        self.asyn_infer_queue = AsyncInferQueue(self.model, jobs=self.num_requests)
        self.asyn_infer_queue.set_callback(self._default_callback)
        # list of list of tuples - (xcenter, ycenter, width, height, class, confidence)
        self._asyn_results: List[AsyncInferenceResult] = []

    def _compile_model(
        self,
        model_path: str,
        camera_selection: CameraOptions,
    ):
        if self.connected:
            raise RuntimeError(f"model {self} already compiled")

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

    def syn(self, input_img):
        """input_img is 2d array (i.e. grayscale img)"""
        input_tensor = [Tensor(np.expand_dims(input_img, (0, 3)), shared_memory=True)]
        output_layer = self.model.output(0)
        return self.model(input_tensor)[output_layer]

    def _default_callback(self, infer_request: InferRequest, userdata: Any) -> None:
        with lock_timeout(self.lock):
            self._asyn_results.append(
                AsyncInferenceResult(
                    id=userdata, result=infer_request.output_tensors[0].data
                )
            )

    def asyn(self, input_img: npt.NDArray, idx: int = None) -> None:
        input_tensor = Tensor(np.expand_dims(input_img, (0, 3)), shared_memory=True)
        self.asyn_infer_queue.start_async({0: input_tensor}, userdata=idx)

    def get_asyn_results(self) -> List[AsyncInferenceResult]:
        with lock_timeout(self.lock, timeout=0.01):
            res = copy(self._asyn_results)
            self._asyn_results = []
            return res

    def wait_all(self):
        self.asyn_infer_queue.wait_all()
