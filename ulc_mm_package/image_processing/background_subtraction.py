""" PatchyBackgroundSubtraction - Find the average image background based on bounding boxes
Find and average pixel values that lay outside bounding boxes across a series of image frames.

#TODO
Remove the dependence on the "BBox" object that is used for this project and just generalize to taking inputs to x/y arrays
"""

# ========================== IMPORTS ======================
from typing import List
import numpy as np

# ========================== CONSTANTS ======================
INSIDE_BBOX_FLAG = 0

class PatchyBackgroundSubtraction:
    def _maskBoxedRegions(
        self,
        img_arr: np.ndarray,
        xmin_vals: List[int],
        xmax_vals: List[int],
        ymin_vals: List[int],
        ymax_vals: List[int],
    ):
        """Set the pixel values of regions inside the bounding boxes to -1 and return the image array.

        Parameters
        ----------
            - img_arr: numpy.ndarray
            - xmin_vals: List[int] - list of the minimum x-values for each bounding box
            - xmax_vals: List[int] - list of the maximum x-values for each bounding box
            - ymin_vals: List[int] - list of the minimum y-values for each bounding box
            - ymax_vals: List[int] - list of the maximum y-values for each bounding box
        """

        for xmin, ymin, xmax, ymax in zip(xmin_vals, ymin_vals, xmax_vals, ymax_vals):
            # Numpy indexing is [row (y), column (x)]
            img_arr[ymin:ymax, xmin:xmax] = INSIDE_BBOX_FLAG

        return img_arr

    def getBackgroundAverageArray(self) -> np.ndarray:
        """Get the averaged background value for each pixel based on the past N frames."""
        return self._backgroundAverageArray


class PatchyBackgroundSubtractionFixedNum(PatchyBackgroundSubtraction):
    def __init__(
        self, img_width: int = 0, img_height: int = 0, num_frames_in_memory: int = 100
    ):
        """A class to store a fixed number of images and continuously update an average background pixel value array.

        The number of frames to retain in memory is set on instantiation. As new images are added, the oldest frames
        are overwritten.

        Parameters
        ----------
        img_width : int
            x dimension of the images to be stored
        img_height : int
            y dimension of the images to be stored
        num_frames_in_memory : int
            Number of images to retain in memory.

        """
        self.frame_storage = np.full(
            (img_height, img_width, num_frames_in_memory), INSIDE_BBOX_FLAG
        )
        self._oldest_frame_ptr = 0
        self._num_frames_in_memory = num_frames_in_memory
        self._backgroundAverageArray = np.zeros((img_height, img_width))
        self.img_counter = np.zeros((img_height, img_width))

    def addImage(self, img_arr, xmin_vals, xmax_vals, ymin_vals, ymax_vals):
        """Add an image to be included in the frame storage.

        If the frame storage is full (i.e already contains `num_frames_in_memory` images),
        the oldest frame is overwritten.

        Parameters
        ----------
        img_arr : an array with the same dimensions specified during class instantiation
        bboxes : list of BoundingBox objects
        """
        masked_img = self._maskBoxedRegions(
            img_arr, xmin_vals, xmax_vals, ymin_vals, ymax_vals
        )
        self._updateBackgroundAverage(masked_img)
        self._addImageToMemory(masked_img)

    def _addImageToMemory(self, img_arr):
        """Writes over the array where the pointer is. Updates the pointer location.

        Slicing in numpy is fast which is why this approach of maintaining a pointer
        and overwriting was chosen (as opposed to using other approaches like keeping a
        FIFO queue, using np.roll, or using append/delete etc.)
        """
        self.frame_storage[:, :, self._oldest_frame_ptr] = img_arr
        self._oldest_frame_ptr = (
            self._oldest_frame_ptr + 1
        ) % self._num_frames_in_memory

    def _updateBackgroundAverage(self, masked_img):
        """Computes the average background value for each pixel.

        Uses Welford's method to compute the updated average (single-pass, so no need to recompute everything). The oldest frame is removed from the average,
        and the new frame is added. Benchmarking on my computer (Macbook Pro 13) this takes ~5us (previously used numpy and that took ~300ms for a
        (800, 600, 100) frame array).
        """
        # Remove the oldest frame from the average ( avg_prev = avg_curr - (avg_curr - old_frame) / N )
        oldest_frame = self.frame_storage[:, :, self._oldest_frame_ptr]
        self.img_counter[oldest_frame != INSIDE_BBOX_FLAG] -= 1
        subtract_step = np.divide(
            (oldest_frame - self._backgroundAverageArray),
            self.img_counter,
            where=self.img_counter != 0,
        )
        subtract_step[oldest_frame == INSIDE_BBOX_FLAG] = 0
        self._backgroundAverageArray = self._backgroundAverageArray - subtract_step

        # Add the newest frame ( avg_new = avg_curr + (new_frame + avg_curr) / (N+1) )
        self.img_counter[masked_img != INSIDE_BBOX_FLAG] += 1
        add_step = np.divide(
            (masked_img - self._backgroundAverageArray),
            self.img_counter,
            where=self.img_counter != 0,
        )
        add_step[masked_img == INSIDE_BBOX_FLAG] = 0
        self._backgroundAverageArray = self._backgroundAverageArray + add_step


class PatchyBackgroundSubtractionContinuous(PatchyBackgroundSubtraction):
    def __init__(self, img_width: int = 0, img_height: int = 0):
        """A class to continuously update an average background pixel value array.

        Parameters
        ----------
        img_width : int
            x dimension of the images to be stored
        img_height : int
            y dimension of the images to be stored
        """
        self._backgroundAverageArray = np.zeros((img_height, img_width))
        self.img_counter = np.zeros((img_height, img_width))

    def addImage(self, img_arr, xmin_vals, xmax_vals, ymin_vals, ymax_vals):
        """Add an image to be included in the average background average.

        Parameters
        ----------
        img_arr : an array with the same dimensions specified during class instantiation
        bboxes : list of BoundingBox objects
        """
        masked_img = self._maskBoxedRegions(
            img_arr, xmin_vals, xmax_vals, ymin_vals, ymax_vals
        )
        self._updateBackgroundAverage(masked_img)

    def _updateBackgroundAverage(self, masked_img):
        """Updates the average background value for each pixel.

        The denominator (when calculating the mean) is only incremented for
        those pixels that were actually part of the background.
        """
        self.img_counter[masked_img != INSIDE_BBOX_FLAG] += 1
        update_step = np.divide(
            (masked_img - self._backgroundAverageArray),
            self.img_counter,
            where=self.img_counter != 0,
        )
        update_step[masked_img == INSIDE_BBOX_FLAG] = 0
        self._backgroundAverageArray = self._backgroundAverageArray + update_step


class MedianBGSubtraction:
    def __init__(
        self, img_height: int = 0, img_width: int = 0, num_frames_in_memory: int = 100
    ):
        """
        A class which stores a fixed number of images (which can be overwritten)
        which returns the pixel-wise median.

        Parameters
        ----------
        img_width : int
            x dimension of the images to be stored
        img_height : int
            y dimension of the images to be stored
        num_frames_in_memory : int
            Number of images to retain in memory.

        """
        self._num_frames_in_memory = num_frames_in_memory
        self.frame_storage = np.zeros((img_height, img_width, num_frames_in_memory))
        self._oldest_frame_ptr = 0
        self._backgroundMedian = 0

    def _addImageToMemory(self, img_arr: np.ndarray):
        """Writes over the array where the pointer is. Updates the pointer location.

        Slicing in numpy is fast which is why this approach of maintaining a pointer
        and overwriting was chosen (as opposed to using other approaches like keeping a
        FIFO queue, using np.roll, or using append/delete etc.)
        """
        self.frame_storage[:, :, self._oldest_frame_ptr] = img_arr
        self._oldest_frame_ptr = (
            self._oldest_frame_ptr + 1
        ) % self._num_frames_in_memory

    def addImage(self, img_arr):
        self._addImageToMemory(img_arr)

    def getMedian(self):
        self._backgroundMedian = np.median(self.frame_storage, axis=2)
        return self._backgroundMedian

    def getVariance(self):
        self._backgroundVariance = np.var(self.frame_storage, axis=2)
        return self._backgroundVariance