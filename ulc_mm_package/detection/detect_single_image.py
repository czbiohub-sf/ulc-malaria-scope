# Lint as: python3
# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Example using TF Lite to detect objects in a given image."""

import argparse
import importlib
import time
import glob
import os
import numpy as np
from PIL import Image
from PIL import ImageDraw
from ulc_mm_package.detection import detect
from ulc_mm_package.detection import utils
from ulc_mm_package.detection.constants_ulc import (
    EDGETPU_SHARED_LIB,
    LUMI_CSV_COLUMNS,
    DEFAULT_CONFIDENCE,
    DEFAULT_INFERENCE_COUNT,
    DEFAULT_FILTER_AREA,
    DEFAULT_IMAGE_FORMAT,
)

def detect_image(
    model,
    use_tpu,
    input_image,
    labels,
    threshold=DEFAULT_CONFIDENCE,
    output=None,
    count=DEFAULT_INFERENCE_COUNT,
    area_filter=DEFAULT_FILTER_AREA,
    filter_background_bboxes=True,
):
    
    labels = utils.load_labels(labels) if labels else {}
    # Import TensorFlow libraries
    # If tflite_runtime is installed, import interpreter from tflite_runtime,
    # else import from regular tensorflow
    # If using Coral Edge TPU, import the load_delegate library
    pkg = importlib.util.find_spec("tflite_runtime")
    if pkg:
        from tflite_runtime.interpreter import Interpreter

        if use_tpu:
            from tflite_runtime.interpreter import load_delegate
    else:
        from tensorflow.lite.python.interpreter import Interpreter

        if use_tpu:
            from tensorflow.lite.python.interpreter import load_delegate

    if use_tpu:
        model, *device = model.split("@")  # noqa
        interpreter = Interpreter(
            model_path=model,
            experimental_delegates=[
                load_delegate(
                    EDGETPU_SHARED_LIB, {"device": device[0]} if device else {}
                )
            ],
        )
    else:
        interpreter = Interpreter(model_path=model)
    interpreter.allocate_tensors()

    image = input_image
    scale = detect.set_input(
        interpreter, image.size, lambda size: image.resize(size, Image.ANTIALIAS)
    )
    numpy_image = np.array(image)
    if filter_background_bboxes:
        numpy_image = numpy_image[:, :, 0]
        thresholded_image = np.zeros(
            (numpy_image.shape[0], numpy_image.shape[1]), dtype=np.uint8
        )
        thresh_value = 128
        thresholded_image[numpy_image < thresh_value] = 1
    for _ in range(count):
        start = time.perf_counter()
        interpreter.invoke()
        inference_time = time.perf_counter() - start
        objs = detect.get_output(interpreter, threshold, scale)
        print("%.2f ms" % (inference_time * 1000))
    filtered_objs = []
    for obj in objs:
        xmin, xmax, ymin, ymax = (
            obj.bbox.xmin,
            obj.bbox.xmax,
            obj.bbox.ymin,
            obj.bbox.ymax,
        )
        org_height, org_width = numpy_image.shape[:2]
        xmin, xmax, ymin, ymax = utils.out_of_bounds(
            xmin, xmax, ymin, ymax, org_width, org_height
        )
        bbox = detect.BBox(xmin, ymin, xmax, ymax)
        obj = detect.Object(
            id=obj.id,
            score=obj.score,
            bbox=bbox
        )
        if obj.bbox.area < area_filter:
            if filter_background_bboxes:
                if utils.check_if_bbox_not_background(bbox, thresholded_image):
                    filtered_objs.append(obj)
            else:
                filtered_objs.append(obj)
    if output is not None:
        image = image.convert("RGB")
        image.save(os.path.join(output, os.path.basename(input_image)))
        utils.draw_objects(ImageDraw.Draw(image), filtered_objs, labels)

    return filtered_objs