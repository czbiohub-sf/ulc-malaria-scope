from typing import Tuple
import numpy as np
import cv2

class FlowRateEstimatorError(Exception):
    """Base class for catching all pressure control related errors."""
    pass

class FlowRateEstimator:

    def __init__(self, img_height: int=600, img_width: int=800, num_image_pairs: int=12, scale_factor: int=10, coeff_of_var_thresh: float=0.8):
        """A class for estimating the flow rate of cells using a 2D cross-correlation.
        The class holds two images at a time in `frame_storage`. To use this class,
        a user needs only to provide a single image at a time. Every two images, 
        the class calculates the displacement between those two.

        Once the specified number of pairs 

        Eaxmple usage (pseudocode)
        ---------------------------

            fre = FlowRateEstimator()

            while im in camera.yieldImages():
                fre.addImageAndCalculatePair()

            if fre.isFull():
                dx, dy = fre.getAverageAndReset()

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

        self.dx = [0] * num_image_pairs
        self.dy = [0] * num_image_pairs
        self.timestamps = [0, 0]
        self.img_height, self.img_width = img_height, img_width
        self.frame_storage = np.zeros((img_height, img_width, 2), dtype=np.uint8)
        self._frame_counter = 0
        self._calc_idx = 0
        self.scale_factor = scale_factor
        self.coeff_of_var_thresh = coeff_of_var_thresh

    def _getAverage(self) -> Tuple[float, float]:
        """Return the mean of the dx and dy displacement arrays"""
        return (np.average(self.dx), np.average(self.dy))

    def _getStandardDeviation(self) -> Tuple[float, float]:
        """Return the standard deviation of the dx and dy displacement arrays"""
        return (np.std(self.dx), np.std(self.dy))

    def getStatsAndReset(self) -> Tuple[float, float, float, float, float, float]:
        """Returns the means and standard deviations of all the values in the x and y displacement arrays
        and then resets the calculation counter.

        A user calling this function should only call it once `isFull` returns True.

        Once `_calc_idx` is reset, it will overwrite previous displacement values stored in dx and dy.
        The `isFull` function will return false until `num_image_pairs' calculations have been done again.

        Returns
        -------
        (float, float, float, float, float, float):
            A tuple of mean (x, y), SD (x, y), and coefficient of variation (cov_x, cov_y)
        """
        self._calc_idx = 0
        mx, my = self._getAverage()
        sd_x, sd_y = self._getStandardDeviation()
        cov_x, cov_y = sd_x / mx, sd_y / my


        if cov_y >= self.coeff_of_var_thresh:
            my = 1

        return (mx, my, sd_x, sd_y, cov_x, cov_y)

    def _addImage(self, img_arr: np.ndarray, timestamp: int):
        """Internal function - add image to the storage with the given timestamp.

        Parameters
        ----------
        img_arr : np.ndarray
            Image to store
        timestamp : int
            Timestamp of when the image was taken (units left to the user)
        """
        self.frame_storage[:, :, self._frame_counter] = img_arr
        self.timestamps[self._frame_counter] = timestamp
        self._frame_counter = (self._frame_counter + 1) % 2

    def _calculatePairDisplacement(self):
        if self._frame_counter == 0 and not self.isFull():
            dx, dy = getFlowrateWithCrossCorrelation(self.frame_storage[:, :, 0], self.frame_storage[:, :, 1], self.scale_factor)
            time_diff = self.timestamps[1] - self.timestamps[0]
            if self.isValidDisplacement(dx, dy):
                self.dx[self._calc_idx] = (dx / time_diff) / (self.img_width / self.scale_factor)
                self.dy[self._calc_idx] = (dy / time_diff) / (self.img_height / self.scale_factor)
                self._calc_idx += 1

    def isValidDisplacement(self, dx, dy) -> bool:
        """A function to check for valid displacement values.

        For now, this function is very simple (i.e only checking for non-negative y-displacement).
        However, if additional logic needs to be implemented, it can go here.
        """
        if dy > 0:
            return True

    def isFull(self) -> bool:
        """Returns True when the calculation (dx, dy) arrays are full.

        The size of `dx` is set during class initialization by the `num_image_pairs` parameter.
        """
        return self._calc_idx >= len(self.dx)

    def addImageAndCalculatePair(self, img: np.ndarray, timestamp: int):
        """A convenience function to add an image and perform a displacement calculation.

        `_calculatePairDisplacement` only runs if two images have been past since the last calculation.
        (I.e there is no chance that two non-temporally-sequential images will be run together).

        Parameters
        ----------
        img_arr : np.ndarray
            Image to store
        timestamp : int
            Timestamp of when the image was taken (units left to the user)
        """
        self._addImage(img, timestamp)
        self._calculatePairDisplacement()


def getFlowrateInPixelsFromBBoxes(prev_bboxes, curr_bboxes, x_tol: int=15):
    """
    Returns the flow rate in number of pixels based on the previous and current frame bounding boxes

    Parameters
    ----------
    prev_bboxes : List[BBox]
        A list of BBox objects from the previous frame
    curr_bboxes : List[BBox]
        A list of BBox objects from the current frame

    Returns
    -------
    int:
        An integer representing the average bounding box displacements found between the previous and current frame

    """
    # Extract relevant parameters from the BBox class
    prev_xmin = np.asarray([bbox.xmin for bbox in prev_bboxes])
    prev_ymin = np.asarray([bbox.ymin for bbox in prev_bboxes])
    prev_xmax = np.asarray([bbox.xmax for bbox in prev_bboxes])
    curr_xmin = np.asarray([bbox.xmin for bbox in curr_bboxes])
    curr_ymin = np.asarray([bbox.ymin for bbox in curr_bboxes])
    curr_xmax = np.asarray([bbox.xmax for bbox in curr_bboxes])

    all_displacements = []

    for i, (c_xmin, c_xmax) in enumerate(zip(curr_xmin, curr_xmax)):
        # If there are multiple bounding boxes in the current frame in the same vertical region
        if np.count_nonzero(np.isclose(curr_xmin, c_xmin, atol=x_tol)) > 1:
            continue

        # Find the bounding box in the previous frame corresponding to the current box
        index_xmin_in_prev_frame = np.argwhere(
            np.isclose(prev_xmin, c_xmin, atol=x_tol) == True
        )
        index_xmax_in_prev_frame = np.argwhere(
            np.isclose(prev_xmax, c_xmax, atol=x_tol) == True
        )

        # Ensure there is only one bounding box in the previous frame which corresponds to the current
        if len(index_xmin_in_prev_frame > 0) and len(index_xmax_in_prev_frame > 0):
            if len(index_xmin_in_prev_frame[0]) == 1:
                # Find the y displacement
                c_ymin = curr_ymin[i]
                p_ymin = prev_ymin[index_xmin_in_prev_frame[0][0]]

                if p_ymin < c_ymin:
                    pixel_displacement = c_ymin - p_ymin
                    all_displacements.append(pixel_displacement)

    return np.average(all_displacements)

def convertPixelToDistance(pixels):
    # TODO
    return 1

def downSampleImage(img: np.ndarray, scale_factor: int):
    """Downsamples an image by `scale_factor`"""
    h, w = img.shape
    return cv2.resize(img, (w // scale_factor, h // scale_factor))

def getTemplateRegion(img: np.ndarray, x1_perc: float=0.05, y1_perc: float=0.05, x2_perc: float=0.45, y2_perc: float=0.85):
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
    xs, xf = int(x1_perc*w), int(x2_perc*w)
    ys, yf = int(y1_perc*h), int(y2_perc*h)

    return img[ys:yf, xs:xf], (xs, xf), (ys, yf)

def getFlowrateWithCrossCorrelation(prev_img: np.ndarray, next_img: np.ndarray, scale_factor: int=10, temp_x1_perc: float=0.05,
temp_y1_perc: float=0.05, temp_x2_perc: float=0.45, temp_y2_perc: float=0.85, debug: bool=False) -> Tuple[float, float]:

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
    """
    im1_ds, im2_ds = downSampleImage(prev_img, scale_factor), downSampleImage(next_img, scale_factor)

    # Select the subregion within the first image by defining which quantiles to use
    im1_ds_subregion, x_offset, y_offset = getTemplateRegion(im1_ds, 0.05, 0.05, 0.85, 0.45)

    # Run a normalized cross correlation between the image to search and subregion
    template_result = cv2.matchTemplate(im2_ds, im1_ds_subregion, cv2.TM_CCOEFF_NORMED)

    # Find the point with the maximum value (i.e highest match) and caclulate the displacement
    _, _, _, max_loc = cv2.minMaxLoc(template_result)
    dx, dy = max_loc[0] - x_offset[0], max_loc[1] - y_offset[0]

    # If debug mode is on, run `plot_cc` which saves images of the cross-correlation calculation.
    if debug:
        plot_cc(im1_ds, im2_ds, im1_ds_subregion, template_result, (x_offset[0], y_offset[0]), (x_offset[1], y_offset[1]), max_loc[0], max_loc[1], dx, dy)

    return dx, dy


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

    h, w = im1_subregion.shape
    im1_subregion = im1_subregion.copy()
    im2_subregion = im2[max_y:max_y+h, max_x:max_x+w].copy()
    im1 = cv2.rectangle(im1, xy1, xy2, 255, 1)
    im2 = cv2.rectangle(im2, (max_x, max_y), (max_x+w, max_y+h), 255, 1)

    fig, ax = plt.subplots(3, 2, figsize=(10, 7))
    ax[0, 0].imshow(im1, cmap='gray')
    ax[0, 1].imshow(im1_subregion, cmap='gray')
    ax[1, 0].imshow(im2, cmap='gray')
    ax[1, 1].imshow(im2_subregion, cmap='gray')
    ax[1, 1].text(0, 0, f"{dx, dy}", bbox={'facecolor': 'white', 'pad': 2})
    ax[2, 0].imshow(template_result)
    plt.show(block=False)
    plt.pause(0.01)
    plt.close()