import os
import numpy as np
from skimage.draw import rectangle
import cv2


def create_dir_if_not_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)


def out_of_bounds(xmin, xmax, ymin, ymax, org_width, org_height):
    if xmin >= org_width:
        xmin = org_width - 1

    if xmin < 0:
        xmin = 0

    if xmax >= org_width:
        xmax = org_width - 1

    if ymin >= org_height:
        ymin = org_height - 1

    if ymin < 0:
        ymin = 0

    if ymax >= org_height:
        ymax = org_height - 1
    return xmin, xmax, ymin, ymax


def load_labels(path, encoding="utf-8"):
    """Loads labels from file (with or without index numbers).

    Args:
    path: path to label file.
    encoding: label file encoding.
    Returns:
    Dictionary mapping indices to labels.
    """
    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()
        if not lines:
            return {}

    if lines[0].split(" ", maxsplit=1)[0].isdigit():
        pairs = [line.split(" ", maxsplit=1) for line in lines]
        return {int(index): label.strip() for index, label in pairs}
    else:
        return {index: line.strip() for index, line in enumerate(lines)}


def draw_objects(frame, objs, labels, colors):
    """Draws the bounding box and label for each object."""
    image_h, image_w, _ = frame.shape
    for obj in objs:
        fontScale = 0.5
        score = obj.score
        class_ind = obj.id
        bbox_color = colors[class_ind]
        cv2.rectangle(
            frame, (obj.bbox.xmin, obj.bbox.ymin), (obj.bbox.xmax, obj.bbox.ymax), bbox_color, 2
        )
        c1 = (obj.bbox.xmin, obj.bbox.ymin)
        fontScale = 0.5
        bbox_thick = int(0.6 * (image_h + image_w) / 600)
        bbox_mess = '%s: %.2f' % (labels.get(class_ind), score)
        t_size = cv2.getTextSize(bbox_mess, 0, fontScale, thickness=bbox_thick // 2)[0]
        c3 = (c1[0] + t_size[0], c1[1] - t_size[1] - 3)
        cv2.rectangle(frame, c1, (int(c3[0]), int(c3[1])), bbox_color, -1)  #filled
        cv2.putText(frame, bbox_mess, (c1[0], int(c1[1] - 2)), cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale, (0, 0, 0), bbox_thick // 2, lineType=cv2.LINE_AA)
    return frame


def check_if_bbox_not_background(bbox, thresholded_image):
    # Draw filled rectangle on the mask image
    mask = np.zeros_like(thresholded_image)
    rr, cc = rectangle(start=(bbox.xmin, bbox.ymin), end=(bbox.xmax, bbox.ymax))
    mask[cc, rr] = 1
    mask_nonzero_area = bbox.area
    intersection = np.logical_and(thresholded_image, mask).astype(np.uint8)
    bbox_is_in_foreground = True
    if (intersection.sum() / mask_nonzero_area) < 0.4:
        bbox_is_in_foreground = False
    return bbox_is_in_foreground
