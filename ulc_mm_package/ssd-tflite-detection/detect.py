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
"""Functions to work with detection models."""

import collections
import cv2
import numpy as np

Object = collections.namedtuple("Object", ["id", "score", "bbox"])


class BBox(collections.namedtuple("BBox", ["xmin", "ymin", "xmax", "ymax"])):
    """Bounding box.

    Represents a rectangle which sides are either
    vertical or horizontal, parallel
    to the x or y axis.
    """

    __slots__ = ()

    @property
    def width(self):
        """Returns bounding box width."""
        return self.xmax - self.xmin

    @property
    def height(self):
        """Returns bounding box height."""
        return self.ymax - self.ymin

    @property
    def area(self):
        """Returns bound box area."""
        return self.width * self.height

    @property
    def valid(self):
        """Returns whether bounding box is valid or not.

        Valid bounding box has xmin <= xmax and
        ymin <= ymax which is equivalent to
        width >= 0 and height >= 0.
        """
        return self.width >= 0 and self.height >= 0

    def scale(self, sx, sy):
        """Returns scaled bounding box."""
        return BBox(
            xmin=sx * self.xmin,
            ymin=sy * self.ymin,
            xmax=sx * self.xmax,
            ymax=sy * self.ymax,
        )

    def translate(self, dx, dy):
        """Returns translated bounding box."""
        return BBox(
            xmin=dx + self.xmin,
            ymin=dy + self.ymin,
            xmax=dx + self.xmax,
            ymax=dy + self.ymax,
        )

    def map(self, f):
        """Returns bounding box modified by applying f for each coordinate."""
        return BBox(
            xmin=f(self.xmin), ymin=f(self.ymin), xmax=f(self.xmax), ymax=f(self.ymax)
        )

    @staticmethod
    def intersect(a, b):
        """Returns the intersection of two bounding boxes (may be invalid)."""
        return BBox(
            xmin=max(a.xmin, b.xmin),
            ymin=max(a.ymin, b.ymin),
            xmax=min(a.xmax, b.xmax),
            ymax=min(a.ymax, b.ymax),
        )

    @staticmethod
    def union(a, b):
        """Returns the union of two bounding boxes (always valid)."""
        return BBox(
            xmin=min(a.xmin, b.xmin),
            ymin=min(a.ymin, b.ymin),
            xmax=max(a.xmax, b.xmax),
            ymax=max(a.ymax, b.ymax),
        )

    @staticmethod
    def iou(a, b):
        """Returns intersection-over-union value."""
        intersection = BBox.intersect(a, b)
        if not intersection.valid:
            return 0.0
        area = intersection.area
        return area / (a.area + b.area - area)


def input_size(interpreter):
    """Returns input image size as (width, height) tuple."""
    _, height, width, _ = interpreter.get_input_details()[0]["shape"]
    return width, height


def input_tensor(interpreter):
    """Returns input tensor view as numpy array of shape (height, width, 3)."""
    tensor_index = interpreter.get_input_details()[0]["index"]
    return interpreter.tensor(tensor_index)()[0]


def set_input(interpreter, size, resize):
    """Copies a resized and properly zero-padded image to the input tensor.

    Args:
    interpreter: Interpreter object.
    size: original image size as (width, height) tuple.
    resize: a function that takes a (width, height) tuple, and returns an RGB
      image resized to those dimensions.
    Returns:
    Actual resize ratio, which should be passed to `get_output` function.
    """
    width, height = input_size(interpreter)
    w, h = size
    scale = min(width / w, height / h)
    w, h = int(w * scale), int(h * scale)
    tensor = input_tensor(interpreter)
    tensor.fill(0)  # padding
    _, _, channel = tensor.shape
    tensor[:h, :w] = np.reshape(resize((w, h)), (h, w, channel))
    return scale, scale


def output_tensor(interpreter, i):
    """Returns output tensor view."""
    tensor = interpreter.tensor(interpreter.get_output_details()[i]["index"])()
    return np.squeeze(tensor)


def get_output(interpreter, score_threshold, image_scale=(1.0, 1.0)):
    """Returns list of detected objects."""
    boxes = output_tensor(interpreter, 0)
    class_ids = output_tensor(interpreter, 1)
    scores = output_tensor(interpreter, 2)
    count = int(output_tensor(interpreter, 3))

    width, height = input_size(interpreter)
    image_scale_x, image_scale_y = image_scale
    sx, sy = width / image_scale_x, height / image_scale_y

    def make(i):
        ymin, xmin, ymax, xmax = boxes[i]
        return Object(
            id=int(class_ids[i]),
            score=float(scores[i]),
            bbox=BBox(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)
            .scale(sx, sy)
            .map(int),
        )

    return [make(i) for i in range(count) if scores[i] >= score_threshold]


def get_output_no_objs(interpreter, score_threshold, image_scale=(1.0, 1.0)):
    """Returns four numpy arrays with information about the image."""

    boxes = output_tensor(interpreter, 0)
    class_ids = output_tensor(interpreter, 1)
    scores = output_tensor(interpreter, 2)
    count = int(output_tensor(interpreter, 3))

    return boxes, class_ids, scores, count


def correct_yolo_boxes(boxes, image_h, image_w, net_h, net_w):
    if (float(net_w) / image_w) < (float(net_h) / image_h):
        new_w = net_w
        new_h = (image_h * net_w) / image_w
    else:
        new_h = net_w
        new_w = (image_w * net_h) / image_h

    for i in range(len(boxes)):
        x_offset, x_scale = (net_w - new_w) / 2.0 / net_w, float(new_w) / net_w
        y_offset, y_scale = (net_h - new_h) / 2.0 / net_h, float(new_h) / net_h

        boxes[i].xmin = int((boxes[i].xmin - x_offset) / x_scale * image_w)
        boxes[i].xmax = int((boxes[i].xmax - x_offset) / x_scale * image_w)
        boxes[i].ymin = int((boxes[i].ymin - y_offset) / y_scale * image_h)
        boxes[i].ymax = int((boxes[i].ymax - y_offset) / y_scale * image_h)


def do_nms(boxes, nms_thresh):
    if len(boxes) > 0:
        nb_class = len(boxes[0].classes)
    else:
        return

    for c in range(nb_class):
        sorted_indices = np.argsort([-box.classes[c] for box in boxes])

        for i in range(len(sorted_indices)):
            index_i = sorted_indices[i]

            if boxes[index_i].classes[c] == 0:
                continue

            for j in range(i + 1, len(sorted_indices)):
                index_j = sorted_indices[j]

                if bbox_iou(boxes[index_i], boxes[index_j]) >= nms_thresh:
                    boxes[index_j].classes[c] = 0


def decode_netout(netout, anchors, obj_thresh, net_h, net_w):
    grid_h, grid_w = netout.shape[:2]
    nb_box = 3
    netout = netout.reshape((grid_h, grid_w, nb_box, -1))

    boxes = []

    netout[..., :2] = _sigmoid(netout[..., :2])
    netout[..., 4] = _sigmoid(netout[..., 4])
    netout[..., 5:] = netout[..., 4][..., np.newaxis] * _softmax(netout[..., 5:])
    netout[..., 5:] *= netout[..., 5:] > obj_thresh

    for i in range(grid_h * grid_w):
        row = i // grid_w
        col = i % grid_w

        for b in range(nb_box):
            # 4th element is objectness score
            objectness = netout[row, col, b, 4]

            if objectness <= obj_thresh:
                continue

            # first 4 elements are x, y, w, and h
            x, y, w, h = netout[row, col, b, :4]

            x = (col + x) / grid_w  # center position, unit: image width
            y = (row + y) / grid_h  # center position, unit: image height
            w = anchors[2 * b + 0] * np.exp(w) / net_w  # unit: image width
            h = anchors[2 * b + 1] * np.exp(h) / net_h  # unit: image height

            # last elements are class probabilities
            classes = netout[row, col, b, 5:]

            box = BoundBox(
                x - w / 2, y - h / 2, x + w / 2, y + h / 2, objectness, classes
            )

            boxes.append(box)

    return boxes


def preprocess_input(image, net_h, net_w):
    new_h, new_w, _ = image.shape

    # determine the new size of the image
    if (float(net_w) / new_w) < (float(net_h) / new_h):
        new_h = (new_h * net_w) // new_w
        new_w = net_w
    else:
        new_w = (new_w * net_h) // new_h
        new_h = net_h

    # resize the image to the new size
    resized = cv2.resize(image[:, :, ::-1] / 255.0, (new_w, new_h))

    # embed the image into the standard letter box
    new_image = np.ones((net_h, net_w, 3)) * 0.5
    new_image[
        (net_h - new_h) // 2 : (net_h + new_h) // 2,
        (net_w - new_w) // 2 : (net_w + new_w) // 2,
        :,
    ] = resized
    new_image = np.expand_dims(new_image, 0)

    return new_image


def normalize(image):
    return image / 255.0


def get_yolo_boxes(model, images, net_h, net_w, anchors, obj_thresh, nms_thresh):
    image_h, image_w, _ = images[0].shape
    nb_images = len(images)
    batch_input = np.zeros((nb_images, net_h, net_w, 3))

    # preprocess the input
    for i in range(nb_images):
        batch_input[i] = preprocess_input(images[i], net_h, net_w)

    # run the prediction
    batch_output = model.predict_on_batch(batch_input)
    batch_boxes = [None] * nb_images

    for i in range(nb_images):
        yolos = [batch_output[0][i], batch_output[1][i], batch_output[2][i]]
        boxes = []

        # decode the output of the network
        for j in range(len(yolos)):
            yolo_anchors = anchors[
                (2 - j) * 6: (3 - j) * 6
            ]  # config['model']['anchors']
            boxes += decode_netout(yolos[j], yolo_anchors, obj_thresh, net_h, net_w)

        # correct the sizes of the bounding boxes
        correct_yolo_boxes(boxes, image_h, image_w, net_h, net_w)

        # suppress non-maximal boxes
        do_nms(boxes, nms_thresh)

        batch_boxes[i] = boxes

    return batch_boxes
