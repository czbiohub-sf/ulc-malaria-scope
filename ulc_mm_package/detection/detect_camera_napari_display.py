# Experiments for fast live update
# https://github.com/VolkerH/NapariPlayground/blob/087fd967288a658d3aedad8b4be76af9e1249bb2/LiveUpdate/webcam_opencv.py
# Adapted from the opencv face detect examples
#
# Volker Hilsenstein at Monash Edu
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
import os
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from PIL import ImageDraw
from qtpy.QtCore import QThread
import napari

import detect
import utils
from rpi_videostream import VideoStream
from constants_ulc import (
    LUMI_CSV_COLUMNS,
    DEFAULT_CONFIDENCE,
    DEFAULT_INFERENCE_COUNT,
    DEFAULT_FILTER_AREA,
    BOX_ANNOTATIONS,
)


class ThreadVideo(QThread):
    def __init__(
        self, layer, shape_layer, videostream, interpreter, output, debug, threshold
    ):
        QThread.__init__(self)
        self.layer = layer
        self.videostream = videostream
        self.interpreter = interpreter
        self.shapes = shape_layer
        self.output = output
        self.debug = debug
        self.threshold = threshold

    def run(self):
        frame_count = 0
        while True:
            frame = self.videostream.read()
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            print(
                "numpy image shape, size, sum {} {} {}".format(
                    image.shape, image.size, np.sum(image)
                )
            )
            image = Image.fromarray(image)
            scale = detect.set_input(
                self.interpreter,
                image.size,
                lambda size: image.resize(size, Image.ANTIALIAS),
            )
            start = time.perf_counter()
            self.interpreter.invoke()
            inference_time = time.perf_counter() - start
            objs = detect.get_output(self.interpreter, self.threshold, scale)
            print("%.2f ms" % (inference_time * 1000))
            input_image = "frame_{}.png".format(frame_count)
            print(input_image)
            numpy_image = np.array(image)
            rects = []
            labels_properties = []
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
                if obj.bbox.area < area_filter:
                    if filter_background_bboxes:
                        if utils.check_if_bbox_not_background(bbox, thresholded_image):
                            df = df.append(
                                {
                                    "image_id": input_image,
                                    "xmin": xmin,
                                    "xmax": xmax,
                                    "ymin": ymin,
                                    "ymax": ymax,
                                    "label": labels.get(obj.id, obj.id),
                                    "prob": obj.score,
                                },
                                ignore_index=True,
                            )
                            filtered_objs.append(obj)
                    else:
                        df = df.append(
                            {
                                "image_id": input_image,
                                "xmin": xmin,
                                "xmax": xmax,
                                "ymin": ymin,
                                "ymax": ymax,
                                "label": labels.get(obj.id, obj.id),
                                "prob": obj.score,
                            },
                            ignore_index=True,
                        )
                        filtered_objs.append(obj)
                    x1 = xmin
                    x2 = xmax
                    y1 = ymin
                    y2 = ymax
                    label = labels.get(obj.id, obj.id)
                    z = frame_count
                    bbox_rect = np.array(
                        [[z, y1, x1], [z, y2, x1], [z, y2, x2], [z, y1, x2]]
                    )
                    rects.append(bbox_rect)
                    labels_properties.append(label)
                self.shapes.data = rects
                self.shapes.properties["box_label"] = np.array(
                    labels_properties, dtype="<U32"
                )
                self.shapes.text.refresh_text(shapes_layer.properties)
                self.layer.data = rgb
                frame_count += 1
            if self.debug:
                image = image.convert("RGB")
                image.save(os.path.join(os.path.abspath(self.output), input_image))
                utils.draw_objects(ImageDraw.Draw(image), filtered_objs, labels)
        df.to_csv(os.path.join(os.path.abspath(output), "preds_val.csv"))


def detect_stream(model, use_tpu, labels, output, resolution, debug, threshold):
    labels = utils.load_labels(labels) if labels else {}
    utils.create_dir_if_not_exists(output)
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

    res_w, res_h = resolution.split("x")
    im_w, im_h = int(res_w), int(res_h)

    # Initialize video stream
    videostream = VideoStream(resolution=(im_w, im_h), framerate=30).start()
    time.sleep(1)
    df = pd.DataFrame(columns=LUMI_CSV_COLUMNS)

    # Initialize frame count calculation
    print("----INFERENCE TIME----")
    with napari.gui_qt():
        # Grab frame from video stream
        frame = videostream.read()
        # initiate viewer, image layer and shape layer
        viewer = napari.Viewer()
        layer = viewer.add_image(frame)
        text_kwargs = {"text": "box_label", "size": 8, "color": "green"}
        add_kwargs = dict(
            face_color="black",
            edge_color="box_label",
            edge_width=3,
            properties={"box_label": BOX_ANNOTATIONS},
            ndim=3,
            text=text_kwargs,
            name="Shapes",
            opacity=0.5,
        )
        shape_layer = viewer.add_shapes(None, **add_kwargs)

        t = ThreadVideo(
            layer, shape_layer, videostream, interpreter, output, debug, threshold
        )
        t.start()


def loop():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-m",
        "--model",
        required=False,
        default="output_tflite_graph.tflite",
        help="File path of .tflite file.",
    )
    parser.add_argument(
        "--edgetpu",
        help="Use Coral Edge TPU Accelerator to speed up detection",
        action="store_true",
    )
    parser.add_argument(
        "-l",
        "--labels",
        required=False,
        default="labels.txt",
        help="File path of labels file.",
    )
    parser.add_argument(
        "-o", "--output", help="File path for the result image with annotations"
    )
    parser.add_argument(
        "--resolution", help="Desired webcam resolution in WxH", default="1280x720"
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help="Score threshold for detected objects.",
    )
    parser.add_argument(
        "--debug",
        help="Enable debug, saves individual frames if enabled",
        action="store_true",
    )

    args = parser.parse_args()
    print(args)
    detect_stream(
        args.model,
        args.edgetpu,
        args.labels,
        args.output,
        args.resolution,
        args.debug,
        args.threshold,
    )


if __name__ == "__main__":
    loop()
