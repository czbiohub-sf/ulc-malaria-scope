#! /usr/bin/env python3

import sys
import time
import threading
import numpy as np
import numpy.typing as npt

from enum import Enum
from pathlib import Path
from copy import deepcopy
from contextlib import contextmanager

from typing import Any, Callable, List, Sequence, Optional, Tuple

from ulc_mm_package.scope_constants import CAMERA_SELECTION

from openvino.preprocess import PrePostProcessor, ResizeAlgorithm
from openvino.runtime import (
    Core,
    Layout,
    Type,
    InferRequest,
    AsyncInferQueue,
    Tensor,
    compile_model,
)


""" TODOs
- All the performance things!
- best place to put autofocus.xml && autofocus.bin? root dir?

See https://github.com/czbiohub/ulc-malaria-autofocus#openvino-performance-optimizations for
more performance things I want to do

Best docs
https://docs.openvino.ai/latest/openvino_docs_OV_UG_Python_API_exclusives.html
"""


class TPUError(Exception):
    pass


class OptimizationHint(Enum):
    LATENCY = 1
    THROUGHPUT = 2


@contextmanager
def lock_timout(lock, timeout=0.01):
    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        lock.release()


class NCSModel:
    """
    Neural Compute Stick 2 Model

    Allows you to run a model (defined by an intel intermediate representation of your
    model, e.g. model.xml & model.bin) on the neural compute stick

    see https://github.com/luxonis/depthai-experiments/pull/57

    Examples
    https://github.com/decemberpei/openvino-ncs2-python-samples/blob/master/async_api_multi-threads.py
    """

    core = None

    def __init_subclass__(cls, *args, **kwargs):
        if NCSModel.core is None:
            NCSModel.core = Core()
        cls.core = NCSModel.core

    def __init__(
        self,
        model_path: str,
        optimization_hint: OptimizationHint = OptimizationHint.THROUGHPUT,
    ):
        """
        params:
            model_path: path to the 'xml' file
        """
        self.lock = threading.Lock()
        self.connected = False
        self.device_name = "MYRIAD"
        self.model = self._compile_model(model_path, optimization_hint)
        self.num_requests = self.model.get_property("OPTIMAL_NUMBER_OF_INFER_REQUESTS")
        self.asyn_infer_queue = AsyncInferQueue(self.model, jobs=self.num_requests)
        self.asyn_infer_queue.set_callback(self._default_callback)
        # list of list of tuples - (xcenter, ycenter, width, height, class, confidence)
        self._asyn_results: List[List[Tuple[int, Tuple[float]]]] = []

    def _compile_model(self, model_path, perf_hint: OptimizationHint):
        if self.connected:
            # TODO: reconnect param?
            return

        model = self.core.read_model(model_path)

        input_tensor_shape = (
            1,
            CAMERA_SELECTION.IMG_HEIGHT,
            CAMERA_SELECTION.IMG_WIDTH,
            1,
        )

        # https://docs.openvino.ai/latest/openvino_docs_OV_UG_Preprocessing_Details.html#resize-image
        ppp = PrePostProcessor(model)
        ppp.input().tensor().set_shape(input_tensor_shape).set_element_type(
            Type.u8
        ).set_layout(Layout("NHWC"))
        ppp.input().model().set_layout(Layout("NCHW"))
        ppp.input().preprocess().resize(ResizeAlgorithm.RESIZE_LINEAR)
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
                    model, self.device_name, {"PERFORMANCE_HINT": perf_hint.name}
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

    def _default_callback(self, infer_request: InferRequest, userdata) -> None:
        with lock_timout(self.lock):
            self._asyn_results.append(infer_request.output_tensors[0].data)

    def syn(self, input_img):
        """input_img is 2d array (i.e. grayscale img)"""
        input_tensor = [Tensor(np.expand_dims(input_img, (0, 3)), shared_memory=True)]
        results = self.model(input_tensor)
        return next(iter(results.values()))

    def asyn(
        self, input_imgs: List[npt.NDArray], idxs: Optional[Sequence[int]] = None
    ) -> None:
        if isinstance(input_imgs, list):
            input_imgs = [
                Tensor(np.expand_dims(img, (0, 3)), shared_memory=True)
                for img in input_imgs
            ]
        else:
            input_imgs = [
                Tensor(np.expand_dims(input_imgs, (0, 3)), shared_memory=True)
            ]

        if idxs is not None:
            assert len(input_imgs) == len(
                idxs
            ), f"must have len(input_imgs) == len(idxs); got {len(input_imgs)} != {len(idxs)}"
        else:
            idxs = range(len(input_imgs))

        for i, input_tensor in zip(idxs, input_imgs):
            self.asyn_infer_queue.start_async({0: input_tensor}, userdata=i)

    def get_asyn_results(self):
        with lock_timout(self.lock):
            res = deepcopy(self._asyn_results)
            self._asyn_results = []
        return res

    def wait_all(self):
        self.asyn_infer_queue.wait_all()


if __name__ == "__main__":
    import cv2

    def _asyn_calling(model, images):
        print("starting asyncing")
        t0 = time.perf_counter()

        for image in images:
            model.asyn(image)

        model.wait_all()

        t1 = time.perf_counter()
        print(f"Total runtime {t1 - t0}")
        print(f"Throughput {len(images) / (t1 - t0)} FPS")

    def _syn_calling(model, images):
        print("starting syncing")
        times = []
        for image in images:
            t0 = time.perf_counter()
            model.syn(image)
            t1 = time.perf_counter()
            times.append(t1 - t0)
        ts = np.asarray(times)
        print(
            f"Total runtime {sum(ts)} \t mean inference {ts.mean()} \t std dev {ts.std()}"
        )
        print(f"Throughput {len(images) / sum(ts)} FPS")

    if len(sys.argv) != 3:
        print(
            f"usage: {sys.argv[0]} <path to model.xml> <path to image or dir of tiffs>"
        )
        exit()

    image_path = Path(sys.argv[2])
    if image_path.is_file():
        images = [cv2.imread(sys.argv[2], cv2.IMREAD_GRAYSCALE)]
    else:
        sorted_fnames = sorted([str(p) for p in image_path.glob("*.tiff")])
        images = [cv2.imread(fname, cv2.IMREAD_GRAYSCALE) for fname in sorted_fnames]

    A = NCSModel(sys.argv[1], OptimizationHint.THROUGHPUT)
    _syn_calling(A, images)
    _asyn_calling(A, images)
