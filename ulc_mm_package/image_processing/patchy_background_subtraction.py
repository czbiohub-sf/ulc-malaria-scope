# ========================= HEADER ===================================
# title             :patchy_background_subtraction.py
# description       :Find and average pixel values that lay outside bounding boxes across a series of image frames. #TODO make a better description
# Main author       :Ilakkiyan Jeyakumar

# ========================== IMPORTS ======================
import numpy as np


# ========================== CONSTANTS ======================
INSIDE_BBOX_FLAG = 0

class PatchyBackgroundSubtraction():

    def _maskBoxedRegions(self, img_arr, bboxes):
        """Set the pixel values of regions inside the bounding boxes to -1 and return the image array.
        
        Parameters
        ----------
            - img_arr: numpy.ndarray
            - bboxes: a list of BoundingBox (BBox) objects
                These objects are defined under the /detection folder
        """


        # Extract relevant parameters from the BBox class
        xmin_vals = np.asarray([bbox.xmin for bbox in bboxes])
        xmax_vals = np.asarray([bbox.xmax for bbox in bboxes])
        ymin_vals = np.asarray([bbox.ymin for bbox in bboxes])
        ymax_vals = np.asarray([bbox.ymax for bbox in bboxes])

        for xmin, ymin, xmax, ymax in zip(xmin_vals, ymin_vals, xmax_vals, ymax_vals):
            # img_arr[xmin:xmax, ymin:ymax] = INSIDE_BBOX_FLAG
            # TODO fix the line below
            img_arr[ymin:ymax, xmin:xmax] = INSIDE_BBOX_FLAG

        return img_arr
        
    def getBackgroundAverageArray(self):
        """Get the averaged background value for each pixel based on the past N frames."""
        self._updateBackgroundAverage()
        return self._backgroundAverageArray

class PatchyBackgroundSubtractionFixedNum(PatchyBackgroundSubtraction):
    def __init__(self, img_width: int=0, img_height: int=0, num_frames_in_memory: int = 100):
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
        self.frame_storage = np.full((img_height, img_width, num_frames_in_memory), INSIDE_BBOX_FLAG)
        self._oldest_frame_ptr = 0
        self._num_frames_in_memory = num_frames_in_memory
        self._backgroundAverageArray = np.zeros((img_height, img_width))

    def addImage(self, img_arr, bboxes):
        """Add an image to be included in the frame storage. 
        
        If the frame storage is full (i.e already contains `num_frames_in_memory` images), 
        the oldest frame is overwritten.

        Parameters
        ----------
        img_arr : an array with the same dimensions specified during class instantiation
        bboxes : list of BoundingBox objects
        """
        masked_img = self._maskBoxedRegions(img_arr, bboxes)
        self._addImageToMemory(masked_img)

    def _addImageToMemory(self, img_arr):
        """Writes over the array where the pointer is. Updates the pointer location.
        
        Slicing in numpy is fast which is why this approach of maintaining a pointer
        and overwriting was chosen (as opposed to using other approaches like keeping a
        FIFO queue, using np.roll, or using append/delete etc.)
        """
        self.frame_storage[:, :, self._oldest_frame_ptr] = img_arr
        self._oldest_frame_ptr = (self._oldest_frame_ptr + 1) % self._num_frames_in_memory

    def _updateBackgroundAverage(self):
        """Computes the average background value for each pixel.
        
        The frame_storage array is an array with shape (height, width, num_frames). Below we take the average for each
        pixel along the num_frames axis. A mask is applied so that pixels which lie inside a bounding box for a particular frame
        are excluded from the averaging calculation. Side note, np.ma.average is used instead of the usual np.average because
        np.ma.average elegantly deals with the (rare) case where all the values along an axis are masked out. The normal np.average 
        would raise a ZeroDivisionError. For more, see: 
            - https://numpy.org/doc/stable/reference/generated/numpy.ma.average.html#numpy.ma.average
            - https://numpy.org/doc/stable/reference/generated/numpy.ma.average.html#numpy.ma.average
        """
        self._backgroundAverageArray = np.ma.average(self.frame_storage, axis=2, weights=(self.frame_storage != INSIDE_BBOX_FLAG)).filled(0)

class PatchyBackgroundSubtractionContinuous(PatchyBackgroundSubtraction):
    def __init__(self, img_width: int=0, img_height: int=0):
        """A class to continuously update an average background pixel value array.

        Parameters
        ----------
        img_width : int
            x dimension of the images to be stored
        img_height : int
            y dimension of the images to be stored
        """
        self._backgroundAverageArray = np.zeros((img_height, img_width))
        self.img_counter = 1

    def addImage(self, img_arr, bboxes):
        """Add an image to be included in the average background average. 

        Parameters
        ----------
        img_arr : an array with the same dimensions specified during class instantiation
        bboxes : list of BoundingBox objects
        """
        masked_img = self._maskBoxedRegions(img_arr, bboxes)
        self._updateBackgroundAverage(masked_img)

    def getBackgroundAverageArray(self):
        """Get the averaged background value for each pixel based on the past N frames."""
        return self._backgroundAverageArray

    def _updateBackgroundAverage(self, masked_img):
        """Updates the average background value for each pixel."""
        self.img_counter += 1
        self._backgroundAverageArray = self._backgroundAverageArray + (masked_img - self._backgroundAverageArray) / self.img_counter