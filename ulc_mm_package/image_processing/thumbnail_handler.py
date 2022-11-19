import numpy as np

from collections import namedtuple
from typing import Any, List, Callable

from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.NCSModel import AsyncInferenceResult


def argmax(arr):
    "faster than np.argmax for small arrays by nearly 30%!"
    return max(range(len(arr)), key=arr.__getitem__)


def flat(l):
    return [y for x in l for y in x]


Thumbnail = namedtuple("Thumbnail", ("class_", "img"))


class ThumbnailHandler:
    def __init__(self):
        self.imgs_under_inference: Dict[Any, np.ndarray] = dict()

    def save_image(self, id: Any, img: np.ndarray):
        self.imgs_under_inference[id] = img

    def process_results(self, results: List[AsyncInferenceResult]) -> List[Thumbnail]:
        return flat([self.process_result(r) for r in results])

    def process_result(self, result: AsyncInferenceResult) -> List[Thumbnail]:
        "TODO: type signature"
        filtered_pred = YOGO.filter_res(result.result)

        img: np.ndarray
        try:
            img = self.imgs_under_inference.pop(result.id)
        except KeyError:
            # TODO logging.warning
            print(f"id {result.id} not found in ThumbnailMmanager.imgs_under_inference")
            return []

        bs, pred_dim, num_preds = filtered_pred.shape
        assert bs == 1, "temporary assertion until batching is better understood on NCS"

        thumbnails: List[Thumbnail] = []
        for i in range(num_preds):
            img_h, img_w = img.shape

            xc, yc, w, h, t0, *classes = filtered_pred[0, :, i]
            xc_px, yc_px, w_px, h_px = img_w * xc, img_h * yc, img_w * w, img_h * h

            x0 = xc_px - w_px / 2
            x1 = xc_px + w_px / 2
            y0 = yc_px - h_px / 2
            y1 = yc_px + h_px / 2

            assert round(y0) != round(y1), "round(y0) == round(y1)"
            assert round(x0) != round(x1), "round(x0) == round(x1)"

            class_ = argmax(classes)
            thumbnail = img[round(y0) : round(y1), round(x0) : round(x1)]

            thumbnails.append(Thumbnail(class_=class_, img=thumbnail))

        return thumbnails


def count_classes(res: AsyncInferenceResult):
    """
    returns a dictionary mapping the class (represented as an integer) to its count
    for the given prediction
    """
    filtered_pred = YOGO.filter_res(res.result)
    class_preds = np.argmax(filtered_pred[0, 5:, :], axis=0)
    unique, counts = np.unique(class_preds, return_counts=True)
    # this dict (raw_counts) will be missing a given class if that class isn't predicted at all
    # this may be confusing and a pain to handle, so just handle it on our side
    raw_counts = dict(zip(unique, counts))
    return {i: raw_counts.get(i, 0) for i in range(len(filtered_pred[0, 5:, 0]))}
