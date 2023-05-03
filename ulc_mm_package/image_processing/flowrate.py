from typing import cast, List, Tuple

import cv2
import numpy as np

from ulc_mm_package.hardware import multiprocess_scope_routine as msr
from ulc_mm_package.image_processing.processing_constants import CORRELATION_THRESH


class FlowRateEstimatorError(Exception):
    """Base class for catching all pressure control related errors."""

    pass


class FlowRateEstimator:
    def __init__(
        self,
        img_height: int = 600,
        img_width: int = 800,
        scale_factor: int = 10,
    ):
        """A class for estimating the flow rate of cells using a 2D cross-correlation.
        The class holds two images at a time in `frame_a` and `frame_b`. To use this class,
        a user needs only to provide a single image at a time. Every two images,
        the class calculates the displacement between those two.

        Once the specified number of pairs

        Eaxmple usage (pseudocode)
        ---------------------------

            fre = FlowRateEstimator()

            while im in camera.yieldImages():
                dx, dy, xcorr_coeff = fre.add_image_and_calculate_pair()

                if fre.is_primed():
                    # Do something with dx, dy, xcorr_coeff
                    (since you need to send at least two images in before fre will return meaningful values)



        Parameters
        ----------
        img_width : int=800 (default)
            x dimension of the images to be stored
        img_height : int=600 (default)
            y dimension of the images to be stored
        num_image_pairs: int=60 (default)
            The number of image pairs for which to calculate flow rate values - this number
            sets the size of the displacement arrays determines when `isFull` returns True.
        """

        self.timestamps: List[float] = [0.0, 0.0]
        self.img_height, self.img_width = img_height, img_width

        # for multi-proc
        self.multiproc_interface = msr.MultiProcFunc.from_arg_definitions(
            get_flowrate_with_cross_correlation,
            work_fn_inputs=[
                msr.get_ctype_image_defn((img_height, img_width)),
                msr.get_ctype_image_defn((img_height, img_width)),
            ],
            work_fn_outputs=[
                msr.get_ctype_float_defn(),
                msr.get_ctype_float_defn(),
                msr.get_ctype_float_defn(),
            ],
        )

        self.frame_a, self.frame_b = self.multiproc_interface._input_ctypes

        self._prev_img: np.ndarray = None
        self.scale_factor = scale_factor

    def reset(self) -> None:
        """Reset initialization booleans."""

        self._prev_img = None

    def is_primed(self) -> bool:
        """Check whether the estimator is ready to return a value."""
        return self.timestamps[0] != 0.0

    def _add_image(self, img_arr: np.ndarray, timestamp: float) -> None:
        """Internal function - add image to the storage with the given timestamp.

        Parameters
        ----------
        img_arr : np.ndarray
            Image to store
        timestamp : int
            Timestamp of when the image was taken (units left to the user)
        """

        # Initialization
        if self._prev_img is None:
            self.frame_a.set(img_arr)
            self.timestamps[1] = timestamp
            self._prev_img = img_arr
        else:
            self.frame_a.set(self._prev_img)
            self.timestamps[0] = self.timestamps[1]

            self.frame_b.set(img_arr)
            self.timestamps[1] = timestamp

            self._prev_img = img_arr

    @staticmethod
    def _convert_to_px_per_unit_time(displacement: float, tdiff: float) -> float:
        return displacement / tdiff

    @staticmethod
    def _convert_to_screen_dim_per_unit_time(
        displacement: float, tdiff: float, scale_factor: float, img_dim: int
    ) -> float:
        return (displacement / tdiff) / (img_dim / scale_factor)

    def _calculate_pair_displacement(self) -> Tuple[float, float, float]:
        """Return dx, dy displacement in px and the cross correlation coefficient ('confidence')"""

        dx, dy, confidence = self.multiproc_interface._func_call()  # type:ignore
        return dx, dy, confidence  # type: ignore

    def add_image_and_calculate_pair(
        self, img: np.ndarray, timestamp: float
    ) -> Tuple[float, float, float]:
        """A convenience function to add an image and perform a displacement calculation.

        Note: The very first measurement returned (after sending only a single image) should be ignored,
        since the displacement calculation will only return a meaningful displacement value once it has a pair of images
        on which to run the cross correlation.

        Parameters
        ----------
        img_arr : np.ndarray
            Image to store
        timestamp : int
            Timestamp of when the image was taken (units left to the user)
        """
        self._add_image(img, timestamp)
        dx, dy, confidence = self._calculate_pair_displacement()

        tdiff = self.timestamps[1] - self.timestamps[0]
        dx = self._convert_to_screen_dim_per_unit_time(
            dx, tdiff, self.scale_factor, self.img_width
        )
        dy = self._convert_to_screen_dim_per_unit_time(
            dy, tdiff, self.scale_factor, self.img_height
        )

        return dx, dy, confidence

    def stop(self):
        self.multiproc_interface.stop()


def downsample_image(img: np.ndarray, scale_factor: int) -> np.ndarray:
    """Downsamples an image by `scale_factor`"""
    h, w = img.shape
    return cv2.resize(img, (w // scale_factor, h // scale_factor))


def get_template_region(
    img: np.ndarray,
    x1_perc: float = 0.05,
    y1_perc: float = 0.05,
    x2_perc: float = 0.85,
    y2_perc: float = 0.45,
):
    """Returns a subregion of the image provided.
    The start and end positions are to be given as percentages of the image's shape.

    Parameters
    ----------
        img : np.ndarray
            An image (i.e a numpy array)
        x1_perc : float
            What percentage of the image the start of the subregion should begin at.
            For example, x1_perc=0.05 of an input image with shape (600, 800) would mean the
            subregion would begin at 0.05*600=30.
        y1_perc: float
            See x1_perc
        x2_perc: float
            See x1_perc
        y2_perc: float
            See x1_perc

    Returns
    -------
        np.ndarray:
            subregion of the input array
        int:
            x_offset (i.e x start of the subregion)
        int:
            y_offset (i.e y start of the subregion)
    """

    h, w = img.shape
    xs, xf = int(x1_perc * w), int(x2_perc * w)
    ys, yf = int(y1_perc * h), int(y2_perc * h)

    return img[ys:yf, xs:xf], (xs, xf), (ys, yf)


def get_flowrate_with_cross_correlation(
    prev_img: np.ndarray,
    next_img: np.ndarray,
    scale_factor: int = 10,
    temp_x1_perc: float = 0.05,
    temp_y1_perc: float = 0.05,
    temp_x2_perc: float = 0.85,
    temp_y2_perc: float = 0.45,
    debug: bool = False,
) -> Tuple[float, float, float]:
    """Find the displacement of a subregion of an image with another, temporally adjacent, image.

    Parameters
    ----------
        prev_img : np.ndarray
            First image
        next_img: np.ndarray
            Subsequent imag
        scale_factor : int
            Factor to use for downsampling the images
        temp_x1_perc : float
            What percentage of the image the start of the subregion should begin at.
            For example, x1_perc=0.05 of an input image with shape (600, 800) would mean the
            subregion would begin at 0.05*600=30.
        temp_y1_perc: float
            See x1_perc
        temp_x2_perc: float
            See x1_perc
        temp_y2_perc: float
            See x1_perc

    Returns
    -------
        int:
            dx: displacement in x
        int:
            dy: displacement in y
        float:
            max_val: maximum value of the cross correlation
    """
    im1_ds, im2_ds = downsample_image(prev_img, scale_factor), downsample_image(
        next_img, scale_factor
    )

    # Select the subregion within the first image by defining which quantiles to use
    im1_ds_subregion, x_offset, y_offset = get_template_region(
        im1_ds, temp_x1_perc, temp_y1_perc, temp_x2_perc, temp_y2_perc
    )

    # Run a normalized cross correlation between the image to search and subregion
    template_result = cv2.matchTemplate(im2_ds, im1_ds_subregion, cv2.TM_CCOEFF_NORMED)

    # Find the point with the maximum value (i.e highest match) and caclulate the displacement
    _, max_val, _, max_loc = cv2.minMaxLoc(template_result)
    dx, dy = max_loc[0] - x_offset[0], max_loc[1] - y_offset[0]

    # If debug mode is on, run `plot_cc` which saves images of the cross-correlation calculation.
    if debug:
        plot_cc(
            im1_ds,
            im2_ds,
            im1_ds_subregion,
            template_result,
            (x_offset[0], y_offset[0]),
            (x_offset[1], y_offset[1]),
            max_loc[0],
            max_loc[1],
            dx,
            dy,
        )

    return float(dx), float(dy), float(max_val)


def plot_cc(im1, im2, im1_subregion, template_result, xy1, xy2, max_x, max_y, dx, dy):
    """A function for debugging and visualizing the cross-correlation
    displacement calculation.

    This function produces a 2x2 plot of:
        Top-left: The first image
        Bottom-left: The second image
        Top-right: A close-up of the subregion of interest in the first image
        Bottom-right: A close-up of the subregion with the closest match in the second image
    """
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    fig, _ = plt.subplots(figsize=(12, 7))
    fig.suptitle("Flow rate xcorr")
    gs = gridspec.GridSpec(3, 6)
    ax1 = plt.subplot(gs[0, 0:3])
    ax2 = plt.subplot(gs[0, 3:])
    ax3 = plt.subplot(gs[1, 0:3])
    ax4 = plt.subplot(gs[1, 3:])
    ax5 = plt.subplot(gs[2, 2:4])

    h, w = im1_subregion.shape
    im1_subregion = im1_subregion.copy()
    im2_subregion = im2[max_y : max_y + h, max_x : max_x + w].copy()
    im1 = cv2.rectangle(im1, xy1, xy2, 255, 1)
    im2 = cv2.rectangle(im2, (max_x, max_y), (max_x + w, max_y + h), 255, 1)

    ax1.imshow(im1, cmap="gray")
    ax2.imshow(im1_subregion, cmap="gray")
    ax3.imshow(im2, cmap="gray")
    ax4.imshow(im2_subregion, cmap="gray")
    ax4.text(0, 0, f"{dx, dy}", bbox={"facecolor": "white", "pad": 2})
    ax5.imshow(template_result)
    plt.show()
    # plt.pause(0.01)
    # plt.close()
