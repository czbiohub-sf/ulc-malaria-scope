#! /usr/bin/env python3

import cv2
import sys
import time
import numpy as np

from enum import Enum
from pathlib import Path

from typing import Any, Callable

from ulc_mm_package.neural_nets.ssaf_constants import IMG_HEIGHT, IMG_WIDTH

from openvino.preprocess import PrePostProcessor, ResizeAlgorithm
from openvino.runtime import Core, Layout, Type, InferRequest, AsyncInferQueue


""" TODOs
- All the performance things!
- Create ABC for Autofocus, obj detect
- best place to put autofocus.xml && autofocus.bin? root dir?

See https://github.com/czbiohub/ulc-malaria-autofocus#openvino-performance-optimizations for
more performance things I want to do
"""


class TPUError(Exception):
    pass


class OptimizationHint(Enum):
    LATENCY = 1
    THROUGHPUT = 2


class NCSModel:
    """
    Neural Compute Stick 2 Model

    Allows you to run a model (defined by an intel intermediate representation of your
    model, e.g. model.xml & model.bin) on the neural compute stick
    """

    def __init__(
        self,
        model_path: str,
        optimization_hint: OptimizationHint = OptimizationHint.THROUGHPUT,
    ):
        """
        params:
            model_path: path to the 'xml' file
        """
        self.device_name = "MYRIAD"
        self.core = Core()
        self.model = self._compile_model(model_path, optimization_hint)
        self.asyn_infer_queue = AsyncInferQueue(self.model)
        self.asyn_infer_queue.set_callback(self._default_callback)
        self.asyn_results = (
            []
        )  # List of list of tuples - (xcenter, ycenter, width, height, class, confidence)

    def _compile_model(self, model_path, perf_hint: OptimizationHint):
        model = self.core.read_model(model_path)

        input_tensor_shape = (1, IMG_HEIGHT, IMG_WIDTH, 1)

        # https://docs.openvino.ai/latest/openvino_docs_OV_UG_Preprocessing_Details.html#resize-image
        ppp = PrePostProcessor(model)
        ppp.input().tensor().set_shape(input_tensor_shape).set_element_type(
            Type.u8
        ).set_layout(Layout("NHWC"))
        ppp.input().model().set_layout(Layout("NCHW"))
        ppp.input().preprocess().resize(ResizeAlgorithm.RESIZE_LINEAR)
        ppp.output().tensor().set_element_type(Type.f32)
        model = ppp.build()

        connection_attempts = 3
        self.connected = False
        while connection_attempts > 0:
            if not self.connected:
                try:
                    compiled_model = self.core.compile_model(
                        model, self.device_name, {"PERFORMANCE_HINT": perf_hint.name}
                    )
                    self.connected = True
                    return compiled_model
                except Exception as e:
                    print(
                        f"Failed to connect NCS: {e}.\nRemaining connection attempts: {connection_attempts}. Retrying..."
                    )
                    connection_attempts -= 1
                    time.sleep(1)

        return -1

    def _default_callback(self, infer_request: InferRequest, userdata) -> None:
        self.asyn_results.append(infer_request.output_tensors[0].data)

    def syn(self, input_img):
        """input_img is 2d array (i.e. grayscale img)"""
        input_tensor = [np.expand_dims(input_img, (0, 3))]
        results = self.model(input_tensor)
        return list(results.values())

    def asyn(
        self,
        input_img: list,
    ) -> None:
        input_tensor = [np.expand_dims(input_img, (0, 3))]
        self.asyn_infer_queue.start_async(input_tensor)

    def get_asyn_results(self):
        res = self.asyn_results
        self.asyn_results = []
        return res


if __name__ == "__main__":

    def _asyn_calling(model, images):
        print("starting asyncing")
        t0 = time.perf_counter()
        for image in images:
            model.asyn(image)
        model.asyn_infer_queue.wait_all()
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

    image_path = Path(sys.argv[1])
    if image_path.is_file():
        images = [cv2.imread(sys.argv[1], cv2.IMREAD_GRAYSCALE)]
    else:
        sorted_fnames = sorted([str(p) for p in image_path.glob("*.tiff")])
        images = [cv2.imread(fname, cv2.IMREAD_GRAYSCALE) for fname in sorted_fnames]

    A = NCSModel("autofocus.xml", OptimizationHint.THROUGHPUT)
    _syn_calling(A, images)
    _asyn_calling(A, images)
