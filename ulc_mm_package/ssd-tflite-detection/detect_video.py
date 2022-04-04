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
import colorsys
import importlib
import random
import time
import os
import pandas as pd
from PIL import Image
from PIL import ImageDraw
from skimage.io import imsave
import cv2
import numpy as np

import detect
import utils
from constants_ulc import (
    EDGETPU_SHARED_LIB,
    LUMI_CSV_COLUMNS,
    DEFAULT_CONFIDENCE,
    DEFAULT_INFERENCE_COUNT,
    DEFAULT_FILTER_AREA,
)


def create_dir_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)


def detect_video_file(
    model,
    use_tpu,
    video,
    labels,
    threshold,
    output,
    count,
    overlaid,
    area_filter,
    filter_background_bboxes,
):
    output = os.path.abspath(output)
    create_dir_if_not_exists(output)
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

    video_path = os.path.abspath(video)
    video = cv2.VideoCapture(video_path)
    freq = cv2.getTickFrequency()

    frame_count = 0
    df = pd.DataFrame(columns=LUMI_CSV_COLUMNS)
    inference_times = []
    parsing_times = []
    num_classes = len(labels)
    hsv_tuples = [(1.0 * x / num_classes, 1., 1.) for x in range(num_classes)]
    colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
    colors = list(map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)), colors))
    random.seed(0)
    random.shuffle(colors)
    random.seed(None)
    while video.isOpened():

        # Acquire frame and resize to expected shape [1xHxWx3]
        ret, image = video.read()
        t1 = cv2.getTickCount()
        if not ret:
            print("Reached the end of the video!")
            break
        np_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(np_image)
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
            # start = time.perf_counter()
            inf_start = time.time()
            interpreter.invoke()
            objs = detect.get_output(interpreter, threshold, scale)
            inf_end = time.time()
            det_time = inf_end - inf_start

        start_time = time.time()
        frame_count += 1
        input_image = os.path.basename(video_path).split(".")[0] + "_{}.png".format(
            frame_count
        )
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
        if overlaid:
            overlaid_image = utils.draw_objects(np_image, filtered_objs, labels, colors)
            imsave(os.path.join(output, os.path.basename(input_image)), overlaid_image)
        t2 = cv2.getTickCount()
        time1 = (t2 - t1) / freq
        frame_rate_calc = 1 / time1
        inference_time = det_time * 1000
        parsing_time = time.time() - start_time
        # Draw performance stats
        print("Inference time: {:.3f} ms".format(inference_time))
        print("OpenCV parsing time: {:.3f} ms".format(parsing_time))
        print("FPS: {:.2f}".format(frame_rate_calc))
        inference_times.append(inference_time)
        parsing_times.append(parsing_time)

    print(
        "inference_time average and std is {} and {}".format(
            np.mean(inference_times), np.std(inference_times)
        )
    )
    print(
        "parsing_time average and std is {} and {}".format(
            np.mean(parsing_times), np.std(parsing_times)
        )
    )
    path = os.path.join(output, "preds_val.csv")
    print("Saving predictions to csv at {}".format(path))
    df.to_csv(path)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-m", "--model", required=True, help="File path of .tflite file."
    )
    parser.add_argument("-v", "--video", required=True, help="Name of the video file")
    parser.add_argument("-l", "--labels", help="File path of labels file.")
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=DEFAULT_CONFIDENCE,
        help="Score threshold for detected objects.",
    )
    parser.add_argument(
        "-o", "--output", help="File path for the result image with annotations"
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=DEFAULT_INFERENCE_COUNT,
        help="Number of times to run inference",
    )
    parser.add_argument(
        "--edgetpu",
        help="Use Coral Edge TPU Accelerator to speed up detection",
        action="store_true",
    )
    parser.add_argument("--overlaid", help="Enable overlaid", action="store_true")
    parser.add_argument(
        "--area_filter",
        help="Enable filtering bounding boxes of area",
        type=int,
        default=DEFAULT_FILTER_AREA,
    )
    parser.add_argument(
        "--filter_background_bboxes",
        help="Enable filtering bounding boxes that are in the background",
        action="store_true",
    )

    args = parser.parse_args()
    print(args)
    detect_video_file(
        args.model,
        args.edgetpu,
        args.video,
        args.labels,
        args.threshold,
        args.output,
        args.count,
        args.overlaid,
        args.area_filter,
        args.filter_background_bboxes,
    )


if __name__ == "__main__":
    main()
