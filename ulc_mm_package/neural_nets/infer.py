import os
import cv2
import sys
import zarr
import time
import argparse

import numpy as np
import allantools as at

from pathlib import Path

from ulc_mm_package.scope_constants import CameraOptions
from ulc_mm_package.neural_nets.NCSModel import NCSModel
from ulc_mm_package.neural_nets.YOGOInference import YOGO
from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus

from typing import Any, List, Generator, Iterable


def _tqdm(iterable, **kwargs):
    return iterable


class ImageLoader:
    def __init__(self, _iter, _num_els):
        self._iter = _iter
        self._num_els = _num_els

    def __iter__(self):
        if self._iter is None:
            raise RuntimeError(
                "instantiate ImageLoader with `load_image_data` or `load_zarr_data`"
            )

        return self._iter()

    def __len__(self):
        if self._iter is None:
            raise RuntimeError(
                "instantiate ImageLoader with `load_image_data` or `load_zarr_data`"
            )

        return self._num_els

    @classmethod
    def load_image_data(cls, path_to_data: str):
        "takes a path to either a single png image or a folder of pngs"
        datapath = Path(path_to_data)
        data = [datapath] if datapath.is_file() else datapath.glob("*.png")

        def _iter():
            for img_name in sorted(data):
                yield cv2.imread(str(img_name), cv2.IMREAD_GRAYSCALE)

        _num_els = 1 if datapath.is_file() else sum(1 for _ in datapath.glob("*.png"))

        return cls(_iter, _num_els)

    @classmethod
    def load_zarr_data(cls, path_to_zarr: str):
        data = zarr.open(path_to_zarr)

        def _iter():
            for i in range(len(data)):
                yield data[i][:]

        _num_els = len(data)

        return cls(_iter, _num_els)

    @classmethod
    def load_random_data(cls, image_shape, n_iters):
        if len(image_shape) == 2:
            image_shape = (1, 1, *image_shape)
        else:
            raise ValueError(f"image shape must be (h,w) - got {image_shape}")

        rand_tensor = np.random.randn(image_shape)

        def _iter():
            for _ in range(n_iters):
                yield rand_tensor

        _num_els = n_iters

        return cls(_iter, _num_els)


def yield_n(itr: Iterable[Any], n: int) -> Generator[List[Any], None, None]:
    if n < 1:
        raise ValueError(f"n must be greater than 1 for yield_n: got {n}")

    values = []
    for val in itr:
        values.append(val)
        if len(values) == n:
            yield values
            values = []


def infer(models, image_loader: ImageLoader):
    for image in image_loader:
        for model in models:
            yield model.syn(image)


def asyn_infer(models, image_loader: ImageLoader):
    for image in image_loader:
        for model in models:
            model.asyn(image)
            yield model.get_asyn_results(timeout=0.001)


def calculate_allan_dev(data, fname):
    ds = at.Dataset(data=data)
    res = ds.compute("tdev")
    taus = res["taus"]
    stat = res["stat"]

    pl = at.Plot()
    pl.plot(ds, errorbars=True, grid=True)
    pl.ax.set_xlabel("frames")
    pl.ax.set_ylabel("Allan Deviation")
    pl.save(fname)


def infer_parser():
    try:
        boolean_action = argparse.BooleanOptionalAction  # type: ignore
    except AttributeError:
        boolean_action = "store_true"  # type: ignore

    parser = argparse.ArgumentParser(description="infer results over some dataset")

    parser.add_argument("--images", type=str, help="path to image or images")
    parser.add_argument("--zarr", type=str, help="path to zarr store")
    parser.add_argument(
        "--model",
        help="choose the model to use for inference",
        default="autofocus",
        const="autofocus",
        nargs="?",
        choices=["autofocus", "yogo", "both"],
    )
    parser.add_argument(
        "--output",
        type=str,
        help="place to write data to",
        default=None,
    )
    parser.add_argument(
        "--allan-dev",
        help="calculate allan deviation",
        action=boolean_action,
        default=False,
    )
    parser.add_argument(
        "--asyn",
        help="run asynchronously",
        action=boolean_action,
        default=False,
    )
    parser.add_argument(
        "--verbose",
        help="print progress bar",
        action=boolean_action,
        default=False,
    )

    return parser


if __name__ == "__main__":
    parser = infer_parser()
    args = parser.parse_args()

    no_imgs = args.images is None
    no_zarr = args.zarr is None
    if (no_imgs and no_zarr) or (not no_imgs and not no_zarr):
        print("you must supply a value for only one of --images or --zarr")
        sys.exit(1)

    if not args.verbose:
        tqdm = _tqdm
    else:
        try:
            from tqdm import tqdm
        except ImportError:
            print("install tqdm for progress bars")
            tqdm = _tqdm

    # hacky way to get dimension of first image
    im = next(
        iter(
            ImageLoader.load_image_data(args.images)
            if no_zarr
            else ImageLoader.load_zarr_data(args.zarr)
        )
    )

    image_loader = (
        ImageLoader.load_image_data(args.images)
        if no_zarr
        else ImageLoader.load_zarr_data(args.zarr)
    )

    if args.allan_dev and args.model != "autofocus":
        raise ValueError("allan deviation can only be used with autofocus")

    if args.model == "autofocus":
        model_classes = [AutoFocus]
    elif args.model == "yogo":
        model_classes = [YOGO]
    elif args.model == "both":
        model_classes = [YOGO, AutoFocus]
    else:
        raise ValueError(f"got invalid value for model: {args.model}")

    if im.shape == (600, 800):
        models = [m(camera_selection=CameraOptions.BASLER) for m in model_classes]
    else:
        models = [m(camera_selection=CameraOptions.AVT) for m in model_classes]

    if args.asyn:
        infer_func = asyn_infer
    else:
        infer_func = infer

    results = []
    if args.output is None:
        for res in infer_func(models, image_loader):
            print(res)
            if args.allan_dev:
                results.append(res)
    else:
        with open(args.output, "w") as f:
            for res in infer_func(models, tqdm(image_loader)):
                f.write(f"{res}\n")
                if args.allan_dev:
                    results.append(res)

    # safety
    [m.wait_all() for m in models]

    if args.allan_dev:
        data_path = Path(
            args.output
            if args.output is not None
            else (args.images if no_zarr else args.zarr)
        )
        fname = data_path.parent / Path(data_path.stem + "_allan_dev").with_suffix(
            ".png"
        )
        calculate_allan_dev(results, str(fname))
