# Experiments for fast live update
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


import numpy as np
from qtpy.QtCore import QThread
import napari
import time
import cv2

import detect
import utils
from rpi_videostream import VideoStream
from constants_ulc import (
    LUMI_CSV_COLUMNS,
    DEFAULT_CONFIDENCE,
    DEFAULT_INFERENCE_COUNT,
    DEFAULT_FILTER_AREA)


class ThreadVideo(QThread):
    def __init__(self, layer, shape_layer, videostream, interpreter):
        QThread.__init__(self)
        self.layer = layer
        self.videostream = videostream
        self.interpreter = interpreter
        self.shapes_ = shape_layer

    def run(self):
        while True:
            frame = videostream.read()
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            print("numpy image shape, size, sum {} {} {}".format(
                image.shape, image.size, np.sum(image)))
            image = Image.fromarray(image)
            scale = detect.set_input(
                interpreter, image.size,
                lambda size: image.resize(size, Image.ANTIALIAS))
            for _ in range(count):
                start = time.perf_counter()
                interpreter.invoke()
                inference_time = time.perf_counter() - start
                objs = detect.get_output(interpreter, threshold, scale)
                print('%.2f ms' % (inference_time * 1000))
            input_image = "frame_{}.png".format(frame_count)
            print(input_image)
            numpy_image = np.array(image)
            if filter_background_bboxes:
                numpy_image = numpy_image[:, :, 0]
                thresholded_image = np.zeros(
                    (numpy_image.shape[0], numpy_image.shape[1]), dtype=np.uint8)
                thresh_value = 128
                thresholded_image[numpy_image < thresh_value] = 1
            filtered_objs = []
            for obj in objs:
                xmin, xmax, ymin, ymax = \
                    obj.bbox.xmin, obj.bbox.xmax, obj.bbox.ymin, obj.bbox.ymax
                org_height, org_width = numpy_image.shape[:2]
                xmin, xmax, ymin, ymax = utils.out_of_bounds(
                    xmin, xmax, ymin, ymax, org_width, org_height)
                bbox = detect.BBox(xmin, ymin, xmax, ymax)
                if obj.bbox.area < area_filter:
                    if filter_background_bboxes:
                        if utils.check_if_bbox_not_background(
                                bbox, thresholded_image):
                            df = df.append(
                                {'image_id': input_image,
                                 'xmin': xmin,
                                 'xmax': xmax,
                                 'ymin': ymin,
                                 'ymax': ymax,
                                 'label': labels.get(obj.id, obj.id),
                                 'prob': obj.score}, ignore_index=True)
                            filtered_objs.append(obj)
                    else:
                        df = df.append(
                            {'image_id': input_image,
                             'xmin': xmin,
                             'xmax': xmax,
                             'ymin': ymin,
                             'ymax': ymax,
                             'label': labels.get(obj.id, obj.id),
                             'prob': obj.score}, ignore_index=True)
                        filtered_objs.append(obj)
            rects = []
            for (xmin, ymin, xmax, ymax) in faces:
                rects.append(
                    np.array([[y, x], [y, x + w], [y + h, x + w], [y + h, x]]))
            self.shapes_.data = rects
            self.layer.data = rgb
            frame_count += 1
            if debug:
                image = image.convert('RGB')
                image.save(
                    os.path.join(os.path.abspath(output), input_image))
                utils.draw_objects(ImageDraw.Draw(image), objs, labels)
        df.to_csv(os.path.join(os.path.abspath(output), "preds_val.csv"))


def detect_stream(
        model, use_tpu,
        labels, threshold, output, count, resolution,
        debug, area_filter, filter_background_bboxes):
    labels = utils.load_labels(labels) if labels else {}
    utils.create_dir_if_not_exists(output)
    # Import TensorFlow libraries
    # If tflite_runtime is installed, import interpreter from tflite_runtime,
    # else import from regular tensorflow
    # If using Coral Edge TPU, import the load_delegate library
    pkg = importlib.util.find_spec('tflite_runtime')
    if pkg:
        from tflite_runtime.interpreter import Interpreter
        if use_tpu:
            from tflite_runtime.interpreter import load_delegate
    else:
        from tensorflow.lite.python.interpreter import Interpreter
        if use_tpu:
            from tensorflow.lite.python.interpreter import load_delegate

    if use_tpu:
        model, *device = model.split('@')  # noqa
        interpreter = Interpreter(
            model_path=model,
            experimental_delegates=[
                load_delegate(
                    EDGETPU_SHARED_LIB,
                    {'device': device[0]} if device else {})])
    else:
        interpreter = Interpreter(model_path=model)

    interpreter.allocate_tensors()

    res_w, res_h = resolution.split('x')
    im_w, im_h = int(res_w), int(res_h)

    # Initialize video stream
    videostream = VideoStream(resolution=(im_w, im_h), framerate=30).start()
    time.sleep(1)
    df = pd.DataFrame(columns=LUMI_CSV_COLUMNS)

    # Initialize frame count calculation
    frame_count = 0
    print('----INFERENCE TIME----')
    with napari.gui_qt():
        # Grab frame from video stream
        frame = videostream.read()
        # initiate viewer, image layer and shape layer
        viewer = napari.Viewer()
        layer = viewer.add_image(frame)
        shape_layer = viewer.add_shapes([])

        t = ThreadVideo(layer, shape_layer, videostream, casc)
        t.start()


def loop():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-m', '--model', required=False,
        default="output_tflite_graph.tflite",
        help='File path of .tflite file.')
    parser.add_argument(
        '--edgetpu',
        help='Use Coral Edge TPU Accelerator to speed up detection',
        action='store_true')
    parser.add_argument(
        '-l', '--labels', required=False,
        default="labels.txt",
        help='File path of labels file.')
    parser.add_argument(
        '-t', '--threshold', type=float, default=DEFAULT_CONFIDENCE,
        help='Score threshold for detected objects.')
    parser.add_argument(
        '-o', '--output',
        help='File path for the result image with annotations')
    parser.add_argument(
        '-c', '--count', type=int, default=DEFAULT_INFERENCE_COUNT,
        help='Number of times to run inference')
    parser.add_argument(
        '--resolution', help='Desired webcam resolution in WxH',
        default='1280x720')
    parser.add_argument(
        '--debug',
        help='Enable debug, saves individual frames if enabled',
        action='store_true')
    parser.add_argument(
        '--area_filter',
        help='Enable filtering bounding boxes of area', type=int,
        default=DEFAULT_FILTER_AREA)
    parser.add_argument(
        '--filter_background_bboxes',
        help='Enable filtering bounding boxes that are in the background',
        action='store_true')

    args = parser.parse_args()
    print(args)
    detect_stream(
        args.model, args.edgetpu,
        args.labels, args.threshold,
        args.output, args.count,
        args.resolution, args.debug,
        args.area_filter, args.filter_background_bboxes)


if __name__ == '__main__':
    loop()
