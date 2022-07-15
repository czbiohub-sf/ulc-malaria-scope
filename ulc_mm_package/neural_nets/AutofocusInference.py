#! /usr/bin/env python3

import cv2
import sys
import time
import numpy as np

from pathlib import Path

from typing import Any, Callable

from openvino.preprocess import PrePostProcessor, ResizeAlgorithm
from openvino.runtime import Core, Layout, Type, InferRequest, AsyncInferQueue


""" TODOs
- Figure out automatic batching if possible on NCS
- Figure out async, iron it out
- type!
- All the performance things!
- Create ABC for Autofocus, obj detect
- best place to put autofocus.xml && autofocus.bin? root dir?

See https://github.com/czbiohub/ulc-malaria-autofocus#openvino-performance-optimizations for
more performance things I want to do
"""


class AutoFocus:
    """
    Autofocus Model

    Allows you to run a model (defined by an intel intermediate representation of your
    model, e.g. model.xml & model.bin) on the neural compute stick

    Very early in development!


    Usage:
        >>> A = AutoFocus("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        >>> A(img)
        <steps from 0!>
    """

    def __init__(self, model_path: str):
        """
        params:
            model_path: path to the 'xml' file
        """
        self.device_name = "MYRIAD"
        self.model = self._compile_model(model_path)
        # async is not ready
        self.async_results = []
        self.infer_queue = None

    def _compile_model(self, model_path):
        core = Core()
        model = core.read_model(model_path)

        input_tensor_shape = (1, 600, 800, 1)

        ppp = PrePostProcessor(model)
        # TODO double check these layouts! NHWC vs NCHW! We train on NHWC, why do we set model layout ot NCHW?
        # ahh https://docs.openvino.ai/latest/openvino_docs_OV_UG_Preprocessing_Details.html#resize-image
        ppp.input().tensor().set_shape(input_tensor_shape).set_element_type(
            Type.u8
        ).set_layout(Layout("NHWC"))
        ppp.input().model().set_layout(Layout("NCHW"))
        ppp.input().preprocess().resize(ResizeAlgorithm.RESIZE_LINEAR)
        ppp.output().tensor().set_element_type(Type.f32)
        model = ppp.build()

        compiled_model = core.compile_model(
            model, self.device_name, {"PERFORMANCE_HINT": "THROUGHPUT"}
        )

        return compiled_model

    @property
    def get_optimal_num_infer_reqs(self):
        return self.model.get_property("OPTIMAL_NUMBER_OF_INFER_REQUESTS")

    def __call__(self, input_img):
        """input_img is 2d array (i.e. grayscale img)"""
        if isinstance(input_img, list):
            input_tensor = [np.expand_dims(img, (0, 3)) for img in input_img]
        else:
            input_tensor = [np.expand_dims(input_img, (0, 3))]

        results = self.model(input_tensor)
        return list(results.values())

    def _default_callback(self, infer_request: InferRequest, *args, **kwargs) -> None:
        t1 = time.perf_counter()
        newval = next(iter(infer_request.results.values()))
        self.async_results.append(newval)

    def asyn(
        self,
        input_img: list,
        cb: Callable[[InferRequest, Any], None] = _default_callback,
        *args,
        **kwargs,
    ) -> None:
        """Works, but not genuinely faster than synchronous"""
        # https://docs.openvino.ai/nightly/openvino_docs_OV_UG_Infer_request.html
        # https://docs.openvino.ai/nightly/openvino_docs_OV_UG_Python_API_exclusives.html
        # https://docs.openvino.ai/nightly/openvino_docs_deployment_optimization_guide_common.html
        if isinstance(input_img, list):
            input_tensors = [np.expand_dims(img, (0, 3)) for img in input_img]
        else:
            input_tensors = [np.expand_dims(input_img, (0, 3))]

        if self.infer_queue is None:
            self.infer_queue = AsyncInferQueue(self.model, len(input_tensors))
            self.infer_queue.set_callback(self._default_callback)

        self.t0 = time.perf_counter()
        for i, input_tensor in enumerate(input_tensors):
            self.infer_queue.start_async({0: input_tensor})


if __name__ == "__main__":
    image_path = Path(sys.argv[1])
    images_per_inference = int(sys.argv[2]) if len(sys.argv) == 3 else 1

    def _asyn_calling(model, images):
        """NEEDS MORE FIDDLING!!!"""
        times = []

        print("starting asyncing")
        t0 = time.perf_counter()

        for image_group in images:
            img_tensors = [
                cv2.imread(image, cv2.IMREAD_GRAYSCALE) for image in image_group
            ]
            model.asyn(img_tensors)

        model.infer_queue.wait_all()

        t1 = time.perf_counter()
        print(model.async_results)
        print(f"done all in {t1 - t0}")
        times.append(t1 - t0)

        ts = np.asarray(times)
        print(
            f"Tot {sum(ts)} Mean inference time: {ts.mean()} Mean Std. Dev {ts.std()}"
        )

    def _syn_calling(model, images):
        times = []
        for image_group in images:
            img_tensors = [
                cv2.imread(image, cv2.IMREAD_GRAYSCALE) for image in image_group
            ]
            t0 = time.perf_counter()
            model(img_tensors)
            t1 = time.perf_counter()
            print(f"done all in {t1 - t0}")
            times.append(t1 - t0)

        ts = np.asarray(times)
        print(
            f"Tot {sum(ts)} Mean inference time: {ts.mean()} Mean Std. Dev {ts.std()}"
        )

    if image_path.is_file():
        images = [[sys.argv[1]]]
    else:
        sorted_fnames = sorted([str(p) for p in image_path.glob("*.tiff")])
        images = [
            sorted_fnames[i : i + images_per_inference]
            for i in range(0, len(sorted_fnames), images_per_inference)
        ]

    A = AutoFocus("autofocus.xml")
    _syn_calling(A, images)
