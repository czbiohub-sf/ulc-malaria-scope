import time
import os

import pandas as pd
from absl import app, flags
from absl.flags import FLAGS
import core.utils as utils
from core.yolov4 import filter_boxes
from tensorflow.python.saved_model import tag_constants
from PIL import Image
import cv2
import numpy as np
from tensorflow.compat.v1 import ConfigProto
import tensorflow as tf
physical_devices = tf.config.experimental.list_physical_devices('GPU')
if len(physical_devices) > 0:
    tf.config.experimental.set_memory_growth(physical_devices[0], True)


flags.DEFINE_string('framework', 'tf', '(tf, tflite, trt')
flags.DEFINE_string('weights', './checkpoints/yolov4-416',
                    'path to weights file')
flags.DEFINE_integer('size', 416, 'resize images to')
flags.DEFINE_boolean('tiny', False, 'yolo or yolo-tiny')
flags.DEFINE_string('model', 'yolov4', 'yolov3 or yolov4')
flags.DEFINE_string('video', './data/road.mp4', 'path to input video')
flags.DEFINE_float('iou', 0.3, 'iou threshold')
flags.DEFINE_float('score', 0.2, 'score threshold')
flags.DEFINE_string('output', None, 'path to output video')
flags.DEFINE_string('output_format', 'XVID', 'codec used in VideoWriter when saving video to file')
flags.DEFINE_boolean('dis_cv2_window', False, 'disable cv2 window during the process') # this is good for the .ipynb


def create_dir_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)


def main(_argv):
    config = ConfigProto()
    config.gpu_options.allow_growth = True
    STRIDES, ANCHORS, NUM_CLASS, XYSCALE = utils.load_config(FLAGS)
    input_size = FLAGS.size
    video_path = FLAGS.video

    print("Video from: ", video_path)
    vid = cv2.VideoCapture(video_path)
    create_dir_if_not_exists(FLAGS.output)

    if FLAGS.framework == 'tflite':
        interpreter = tf.lite.Interpreter(model_path=FLAGS.weights)
        interpreter.allocate_tensors()
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        print(input_details)
        print(output_details)
    else:
        saved_model_loaded = tf.saved_model.load(FLAGS.weights, tags=[tag_constants.SERVING])
        infer = saved_model_loaded.signatures['serving_default']

    frame_id = 0
    exec_times = []
    dfs = []
    last_start_time = time.perf_counter()
    while True:
        return_value, frame = vid.read()
        if return_value:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
        else:
            if frame_id == vid.get(cv2.CAP_PROP_FRAME_COUNT):
                print("Video processing complete")
                break
            raise ValueError("No image! Try with another video format")

        image_data = cv2.resize(frame, (input_size, input_size))
        image_data = image_data / 255.
        image_data = image_data[np.newaxis, ...].astype(np.float32)
        prev_time = time.perf_counter()

        if FLAGS.framework == 'tflite':
            interpreter.set_tensor(input_details[0]['index'], image_data)
            interpreter.invoke()
            pred = [interpreter.get_tensor(output_details[i]['index']) for i in range(len(output_details))]
            if FLAGS.model == 'yolov3' and FLAGS.tiny:
                boxes, pred_conf = filter_boxes(pred[1], pred[0], score_threshold=0.25,
                                                input_shape=tf.constant([input_size, input_size]))
            else:
                boxes, pred_conf = filter_boxes(pred[0], pred[1], score_threshold=0.25,
                                                input_shape=tf.constant([input_size, input_size]))
        else:
            batch_data = tf.constant(image_data)
            pred_bbox = infer(batch_data)
            for key, value in pred_bbox.items():
                boxes = value[:, :, 0:4]
                pred_conf = value[:, :, 4:]

        boxes, scores, classes, valid_detections = tf.image.combined_non_max_suppression(
            boxes=tf.reshape(boxes, (tf.shape(boxes)[0], -1, 1, 4)),
            scores=tf.reshape(
                pred_conf, (tf.shape(pred_conf)[0], -1, tf.shape(pred_conf)[-1])),
            max_output_size_per_class=100,
            max_total_size=100,
            iou_threshold=FLAGS.iou,
            score_threshold=FLAGS.score
        )
        pred_bbox = [boxes.numpy(), scores.numpy(), classes.numpy(), valid_detections.numpy()]
        image, objects = utils.draw_bbox(frame, pred_bbox)
        exec_time = (time.perf_counter() - prev_time) * 1000
        exec_times.append(exec_time)
        result = np.asarray(image)
        info = "time: %.2f ms" % (exec_time)
        print(info)

        result = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        if not FLAGS.dis_cv2_window:
            cv2.namedWindow("result", cv2.WINDOW_AUTOSIZE)
            cv2.imshow("result", result)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        if FLAGS.output:
            image = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
            output_img_name = os.path.join(
                os.path.abspath(FLAGS.output), "result_{}.jpg".format(frame_id)
            )
            cv2.imwrite(output_img_name, image)
            for obj in objects:
                dfs.append(
                    pd.DataFrame.from_records(
                        [
                            {
                                "image_id": output_img_name,
                                "xmin": obj["xmin"],
                                "xmax": obj["xmax"],
                                "ymin": obj["ymin"],
                                "ymax": obj["ymax"],
                                "label": obj["class_id"],
                                "prob": obj["prob"]
                            }
                        ]
                    )
                )
        frame_id += 1
        print("FPS is", frame_id / (time.perf_counter() - last_start_time))
    print(
        "exec_time average and std is {} and {} ms".format(
            np.mean(exec_times), np.std(exec_times)
        )
    )
    df = pd.concat(dfs)
    df.to_csv(os.path.join(os.path.abspath(FLAGS.output), "bb_labels.csv"), index=False)


if __name__ == '__main__':
    try:
        app.run(main)
    except SystemExit:
        pass
