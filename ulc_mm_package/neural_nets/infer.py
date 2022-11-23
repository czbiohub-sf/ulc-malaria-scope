import cv2
import zarr
import argparse

import numpy as np
import allantools as at

from pathlib import Path

from ulc_mm_package.neural_nets.AutofocusInference import AutoFocus
from ulc_mm_package.scope_constants import CameraOptions

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
            image_shape = (1,1,*image_shape)
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


def infer(model, image_loader: ImageLoader):
    for image in image_loader:
        model.asyn(image)
        yield model.get_asyn_results(timeout=0.001)


def batch_infer(model, image_loader: ImageLoader):
    for images in yield_n(image_loader, 4):
        yield model(images)


def manual_batch_infer(model, image_loader: ImageLoader):
    for images in yield_n(image_loader, 4):
        image = np.stack(images)
        yield model(image)

def no_infer(model, image_loader: ImageLoader):
    for image in image_loader:
        yield 0

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
        "--verbose",
        help="print progress bar",
        action=boolean_action,
        default=False,
    )

    return parser


if __name__ == "__main__":
    import sys

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

    if im.shape == (600, 800):
        A = AutoFocus(camera_selection=CameraOptions.BASLER)
    else:
        A = AutoFocus(camera_selection=CameraOptions.AVT)

    import os
    import time
    batch_type = os.environ.get("MS_BATCH", "").lower()
    if batch_type == 'batch':
        infer_func = batch_infer
    elif batch_type == 'manual_batch':
        infer_func = manual_batch_infer
    elif batch_type == 'no_infer':
        infer_func = no_infer
    else:
        infer_func = infer

    print(f"using {infer_func}")
    print(f"num streams {A.core.get_property('MYRIAD', 'NUM_STREAMS')}")
    print(f"perf hint {A.model.get_property('PERFORMANCE_HINT')}")
    print(f"optim.num req {A.model.get_property('OPTIMAL_NUMBER_OF_INFER_REQUESTS')}")

    results = []

    if args.output is None:
        for res in infer_func(A, image_loader):
            print(res)
            if args.allan_dev:
                results.append(res)
    else:
        with open(args.output, "w") as f:
            for res in infer_func(A, tqdm(image_loader)):
                f.write(f"{res}\n")
                if args.allan_dev:
                    results.append(res)

    t0 = time.perf_counter()
    print("about to wait")
    A.wait_all()
    t1 = time.perf_counter()
    print(f"waiting for {t1 - t0} secs")

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

    print("all done in infer.py")
