#!/usr/bin/env python
"""
    openvino sync
"""
from __future__ import print_function, division

import glob
import logging
import os
import sys
import time
from argparse import ArgumentParser, SUPPRESS
from time import perf_counter
import importlib
import tensorflow as tf

import cv2
import numpy as np
import pandas as pd

import detect

logging.basicConfig(
    format="[ %(levelname)s ] %(message)s", level=logging.INFO, stream=sys.stdout
)
log = logging.getLogger()

VIDEO_EXTS = [".avi", ".m4v", ".mkv", ".mp4"]
IMAGE_EXTS = [".png", ".jpg", ".tif", ".tiff"]
SIZE = 416


def build_argparser():
    parser = ArgumentParser(add_help=False)
    args = parser.add_argument_group("Options")
    args.add_argument(
        "-m",
        "--model",
        help="Required. Path to an .xml file with a trained model.",
        type=str,
    )
    args.add_argument("--labels", help="Optional. Labels mapping files", type=str)

    args.add_argument(
        "-h",
        "--help",
        action="help",
        default=SUPPRESS,
        help="Show this help message and exit.",
    )
    args.add_argument(
        "-t",
        "--prob_threshold",
        help="Optional. Probability threshold for detections filtering",
        default=0.3,
        type=float,
    )
    args.add_argument(
        "-iout",
        "--iou_threshold",
        help="Optional. Intersection over union threshold for overlapping "
        "detections filtering",
        default=0.3,
        type=float,
    )
    args.add_argument(
        "-ni",
        "--number_iter",
        help="Optional. Number of inference iterations",
        default=1,
        type=int,
    )
    args.add_argument(
        "-pc",
        "--perf_counts",
        help="Optional. Report performance counters",
        default=False,
        action="store_true",
    )
    args.add_argument(
        "-r",
        "--raw_output_message",
        help="Optional. Output inference results raw values showing",
        default=False,
        action="store_true",
    )
    args.add_argument(
        "-i",
        "--input",
        help="Path to video file or image or a folder of images. Default webcam i.e 'cam'",
        default="cam",
        type=str,
    )
    args.add_argument(
        "--edgetpu",
        help="Use Coral Edge TPU Accelerator to speed up detection",
        action="store_true",
    )
    args.add_argument(
        "-o",
        "--output",
        help="File path for the result image with annotations and csv file containing bboxes, annotations",
    )
    args.add_argument(
        "-f", "--format", type=str, default=".jpg", help="Format of image"
    )
    return parser


def create_dir_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)


if __name__ == "__main__":
    args = build_argparser().parse_args()
    # Import TensorFlow libraries
    # If tflite_runtime is installed, import interpreter from tflite_runtime,
    # else import from regular tensorflow
    # If using Coral Edge TPU, import the load_delegate library
    pkg = importlib.util.find_spec("tflite_runtime")
    use_tpu = args.edgetpu
    model = args.model
    iou_threshold = args.iou_threshold
    if pkg:
        from tflite_runtime.interpreter import Interpreter

        print("tflite_runtime package is present")
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
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print(input_details)
    print(output_details)
    conf = args.prob_threshold
    input_images = []
    video_file = False
    if args.input == "cam":
        input_stream = 0
        cap = cv2.VideoCapture(input_stream)
        video_file = True
    if args.format in VIDEO_EXTS:
        input_stream = args.input
        cap = cv2.VideoCapture(input_stream)
        assert os.path.isfile(args.input), "Specified input file doesn't exist"
        video_file = True
    cv2.namedWindow("frame", cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    last_start_time = perf_counter()
    count_frame = 0
    fps_time = 0
    dfs = []
    if args.labels:
        with open(args.labels, "r") as f:
            labels_map = [x.strip() for x in f]
    else:
        labels_map = None

    create_dir_if_not_exists(args.output)
    inference_times = []
    parsing_times = []
    if video_file:
        while cap.isOpened():
            ret, frame = cap.read()
            output_img_name = os.path.join(
                args.output, "result_{}.jpg".format(count_frame)
            )
            if not ret:
                break
            start_time = perf_counter()
            image_data = cv2.resize(frame, (SIZE, SIZE))
            image_data = image_data / 255.0
            image_data = image_data[np.newaxis, ...].astype(np.float32)
            interpreter.set_tensor(input_details[0]["index"], image_data)
            interpreter.invoke()
            pred = [
                interpreter.get_tensor(output_details[i]["index"])
                for i in range(len(output_details))
            ]
            inference_time = time.time() - start_time
            parsing_time_begins = time.time()
            objects = detect.handle_predictions(pred[0], conf, iou_threshold)
            print(objects)
            all_time = perf_counter() - start_time
            parsing_time = time.time() - parsing_time_begins
            all_time = perf_counter() - start_time
            print("The processing time of one frame is", all_time)
            cv2.imwrite(output_img_name, frame)
            count_frame = count_frame + 1
            print("FPS is", count_frame / (perf_counter() - last_start_time))
            cv2.imshow("frame", frame)
            for obj in objects:
                dfs.append(
                    pd.DataFrame.from_records(
                        [
                            {
                                "filename": output_img_name,
                                "xmin": obj["xmin"],
                                "xmax": obj["xmax"],
                                "ymin": obj["ymin"],
                                "ymax": obj["ymax"],
                                "class": labels_map[obj["class_id"]],
                            }
                        ]
                    )
                )
            inference_times.append(inference_time)
            parsing_times.append(parsing_time)

            key = cv2.waitKey(3)
            if key == 27:
                break
    else:
        input_images = glob.glob(os.path.join(args.input, "*" + args.format))
        for img_name in input_images:
            frame = cv2.imread(img_name)
            output_img_name = os.path.join(args.output, os.path.basename(img_name))
            start_time = perf_counter()
            image_data = cv2.resize(frame, (SIZE, SIZE))
            image_data = image_data / 255.0
            image_data = image_data[np.newaxis, ...].astype(np.float32)
            interpreter.set_tensor(input_details[0]["index"], image_data)
            interpreter.invoke()
            pred = [
                interpreter.get_tensor(output_details[i]["index"])
                for i in range(len(output_details))
            ]
            inference_time = time.time() - start_time
            parsing_time_begins = time.time()
            objects = detect.handle_predictions(pred[0], conf, iou_threshold)
            all_time = perf_counter() - start_time
            parsing_time = time.time() - parsing_time_begins
            print("The processing time of one frame is {} ms".format(all_time))
            cv2.imwrite(output_img_name, frame)
            count_frame = count_frame + 1
            print("FPS is", count_frame / (perf_counter() - last_start_time))
            cv2.imshow("frame", frame)
            for obj in objects:
                dfs.append(
                    pd.DataFrame.from_records(
                        [
                            {
                                "filename": output_img_name,
                                "xmin": obj["xmin"],
                                "xmax": obj["xmax"],
                                "ymin": obj["ymin"],
                                "ymax": obj["ymax"],
                                "class": labels_map[obj["class_id"]],
                            }
                        ]
                    )
                )
            inference_times.append(inference_time)
            parsing_times.append(parsing_time)

            key = cv2.waitKey(3)
            if key == 27:
                break
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

    df = pd.concat(dfs)
    df.to_csv(os.path.join(os.path.abspath(args.output), "bb_labels.csv"), index=False)
    cv2.destroyAllWindows()
