#! /usr/bin/env python3

from ulc_mm_package.neural_nets.NCSModel import NCSModel, OptimizationHint
from ulc_mm_package.neural_nets.neural_network_constants import AUTOFOCUS_MODEL_DIR
from ulc_mm_package.scope_constants import CameraOptions, CAMERA_SELECTION


class AutoFocus(NCSModel):
    """
    Autofocus Model

    Usage:
        >>> A = AutoFocus("model.xml")  # the model.bin file should be in same dir
        >>> img = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
        >>> A(img)
        <steps from 0!>
    """

    def __init__(
        self,
        model_path: str = AUTOFOCUS_MODEL_DIR,
        camera_selection: CameraOptions = CAMERA_SELECTION,
    ):
        super().__init__(
            model_path=model_path,
            optimization_hint=OptimizationHint.LATENCY,
            camera_selection=camera_selection,
        )

    def __call__(self, input_img):
        return self.syn(input_img)[0][0]


if __name__ == "__main__":
    import time
    import cv2
    import sys
    from pathlib import Path
    from ulc_mm_package.scope_constants import CameraOptions

    ex = cv2.imread(str(next(Path(sys.argv[1]).glob("*.png"))), cv2.IMREAD_GRAYSCALE)

    if ex.shape == (600, 800):
        A = AutoFocus(camera_selection=CameraOptions.BASLER)
    else:
        A = AutoFocus(camera_selection=CameraOptions.AVT)

    ts = []
    for imgpath in sorted(Path(sys.argv[1]).glob("*.png")):
        im = cv2.imread(str(imgpath), cv2.IMREAD_GRAYSCALE)

        t0 = time.perf_counter()
        r = A(im)
        dt = time.perf_counter() - t0
        ts.append(dt)
        print(r)

    print(f"avg dt: {sum(ts) / len(ts)}")
    print(f"min dt: {min(ts)}")
    print(f"max dt: {max(ts)}")
    print(f"avg fps: {len(ts) / sum(ts)}")
    time.sleep(5)
