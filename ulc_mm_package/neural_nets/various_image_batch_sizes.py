#! /usr/bin/env python3

import os
import sys
import time

from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus
from ulc_mm_package.neural_nets.infer import ImageLoader, yield_n, infer_parser, _tqdm
from ulc_mm_package.scope_constants import CameraOptions

from typing import Any, List, Generator, Iterable


def yield_n(itr: Iterable[Any], n: int) -> Generator[List[Any], None, None]:
    if n < 1:
        raise ValueError(f"n must be greater than 1 for yield_n: got {n}")

    values = []
    for val in itr:
        values.append(val)
        if len(values) == n:
            yield values
            values = []


def syn_batch_infer(model, image_loader: ImageLoader, n: int = 4):
    for images in yield_n(image_loader, n):
        t0 = time.perf_counter()
        r = model.syn_batch(images)
        t1 = time.perf_counter()
        yield r, t1 - t0


def syn_infer(model, image_loader: ImageLoader, n: int = 4):
    for images in image_loader:
        t0 = time.perf_counter()
        r = model.syn(images)
        t1 = time.perf_counter()
        yield r, t1 - t0


if __name__ == "__main__":
    parser = infer_parser()
    args = parser.parse_args()

    if args.verbose:
        from tqdm import tqdm
    else:
        tqdm = _tqdm

    imgs_path = args.images

    im = next(iter(ImageLoader.load_image_data(imgs_path)))

    if im.shape == (600, 800):
        A = AutoFocus(camera_selection=CameraOptions.BASLER)
    else:
        A = AutoFocus(camera_selection=CameraOptions.AVT)

    dts = []
    results = []
    image_loader = ImageLoader.load_image_data(imgs_path)

    for (r, dt) in tqdm(syn_infer(A, image_loader), total=len(image_loader)):
        results.append(r)
        dts.append(dt)

    print(
        f"syn: mean inference time: {sum(dts) / len(dts)} throughput {len(image_loader) * sum(dts) / len(dts)}"
    )

    for i in range(1, 24):
        results = []
        dts = []

        image_loader = ImageLoader.load_image_data(imgs_path)
        for (r, dt) in tqdm(
            syn_batch_infer(A, image_loader, i), total=len(image_loader) / i
        ):
            results.extend([v.result for v in r])
            dts.append(dt)

        mean_inf_time = sum(dts) / len(dts)
        tput = len(image_loader) / sum(dts)
        print(f"{i}: mean inference time: {mean_inf_time} throughput {tput}")
