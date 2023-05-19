#! /usr/bin/env python3

import argparse
import numpy as np
import matplotlib.pyplot as plt

from PIL import Image, ImageDraw
from pathlib import Path
from typing import Tuple

from ulc_mm_package.neural_nets import YOGOInference as yg
from ulc_mm_package.neural_nets.neural_network_constants import YOGO_CLASS_LIST


def bbox_colour(label: str, opacity: float = 1.0) -> Tuple[int, int, int, int]:
    if not (0 <= opacity <= 1):
        raise ValueError(f"opacity must be between 0 and 1, got {opacity}")
    if label in ("healthy", "0"):
        return (0, 255, 0, int(opacity * 255))
    elif label in ("misc", "6"):
        return (0, 0, 0, int(opacity * 255))
    return (255, 0, 0, int(opacity * 255))


def bbox_convert(xc, yc, w, h, img_h, img_w) -> Tuple[int, int, int, int]:
    return (
        img_w * (xc - w / 2),
        img_h * (yc - h / 2),
        img_w * (xc + w / 2),
        img_h * (yc + h / 2),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "image_dir",
        help="directory of images",
        type=Path,
    )
    parser.add_argument(
        "--threshold",
        help="objectness threshold - float between 0 and 1 (default 0.5)",
        type=float,
        default=0.5,
    )
    args = parser.parse_args()

    model = yg.YOGO()
    for image_path in args.image_dir.iterdir():
        if image_path.is_file() and image_path.name.endswith(".png"):
            pil_img = Image.open(image_path)
            image = np.array(pil_img)[None, None, :, :]
            image = model.crop_img(image)
            img_h, img_w = image.shape[2:]

            predictions = model.syn(image)
            predictions = predictions[0, ...]
            predictions = model.filter_res(predictions, threshold=args.threshold)
            predictions = predictions.T

            rgb = Image.new("RGBA", image.size[2:])
            rgb.paste(image)
            draw = ImageDraw.Draw(rgb)

            for r in predictions:
                label_idx = np.argmax(r[5:])
                label = YOGO_CLASS_LIST[label_idx]
                draw.rectangle(
                    bbox_convert(r[0], r[1], r[2], r[3], img_h, img_w),
                    outline=bbox_colour(label),
                )
                draw.text((r[0], r[1]), label, (0, 0, 0, 255))

            plt.imshow(draw)
            plt.show()
