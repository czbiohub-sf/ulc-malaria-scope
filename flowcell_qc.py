import glob
import os
import sys
from argparse import ArgumentParser
import xlsxwriter

import cv2
import numpy as np
from scipy import ndimage

MIN_HUE = 76
MAX_HUE = 255
DEFAULT_IMAGE_FORMAT = "png"
MORPHOLOGY_KERNEL = np.ones((10, 10), np.uint8)
XLSX_SPACING = 2


def get_parser():
    parser = ArgumentParser()
    # Example command
    # python3 flowcell_qc.py --input /Users/pranathi.vemuri/Desktop/flowcell_images/ --image_format png
    parser.add_argument(
        "-i", "--input",
        help="Path to folder containing flowcell images",
        type=str)
    parser.add_argument(
        "--image_format",
        help="format of images",
        type=str,
        default=DEFAULT_IMAGE_FORMAT)
    parser.add_argument(
        "--min_hue",
        help="Minimum hue",
        type=int,
        default=MIN_HUE)
    parser.add_argument(
        "--max_hue",
        help="Maximum hue",
        type=int,
        default=MAX_HUE)
    return parser


def binarize_by_hue_filter(
        rgb_flowcell_image,
        min_hue,
        max_hue):
    """
    Returns a binarized image after
    1) converting the rgb rgb_flowcell_image to hsv space
    2) setting a range of gray pixels in hue
       channel to 255, and the rest to zeros
    3) erode and dilate to remove touching objects in flowcell and
      remove any morphological holes respectively in the objects in flowcell

    Refer to below links to understand hsv space and thresholding in hsv space
    https://www.lifewire.com/what-is-hsv-in-design-1078068
    https://docs.opencv.org/3.4/da/d97/tutorial_threshold_inRange.html

    Args:
        rgb_flowcell_image: np.array
            image in rgb space to binarize
        min_hue: int
            lower limit in hue
        max_hue: int
            upper limit in hue

    Returns:
       binary_flowcell_image: np.array
        binarized mosquito image after filtering in hsv space objects in flowcell are in
        black and the saturatedbackground is 255
    """
    # convert to hsv space
    hsv = cv2.cvtColor(rgb_flowcell_image, cv2.COLOR_RGB2HSV)
    # setting a range in hsv space to 255, and the rest to zeros
    # - using default range,
    # sets the background to 255 and objects in flowcell to zero
    lower_range = np.array([min_hue, 0, 0])
    upper_range = np.array([max_hue, 255, 255])
    mask = cv2.inRange(hsv, lower_range, upper_range)
    # Erode to remove two touching objects in flowcell
    eroded = cv2.morphologyEx(mask, cv2.MORPH_ERODE, MORPHOLOGY_KERNEL, 2)
    # Dilate to remove any morphological holes
    dilated = cv2.morphologyEx(mask, cv2.MORPH_DILATE, MORPHOLOGY_KERNEL, 1)

    binary_flowcell_image = np.logical_and(eroded, dilated).astype(np.uint8)
    return binary_flowcell_image.astype(np.uint8)


def count_regions_in_center_of_image(rgb_flowcell_image, binary_flowcell_image):
    center_x = binary_flowcell_image.shape[0] // 2
    center_y = binary_flowcell_image.shape[1] // 2
    central_subset = binary_flowcell_image[
        center_x - 300: center_x + 300,
        center_y - 300: center_y + 300]
    _, objs = ndimage.label(central_subset)
    central_subset_rgb = rgb_flowcell_image[center_x - 200: center_x + 200, center_y - 200: center_y + 200, :]
    return central_subset_rgb, central_subset, objs


def write_xlsx(path, spacing, subset_images, central_subset_rgbs, num_inference_objects):
    workbook = xlsxwriter.Workbook(os.path.join(path, "inference_fringes_stats.xlsx"))
    worksheet = workbook.add_worksheet("sheet1")

    worksheet.set_column("A:A", 30)
    worksheet.set_column("B:B", 10)
    temp_folder = os.path.join(path, "predict_temp_central_flowcell")
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)
    else:
        print("Path {} already exists, might be overwriting data".format(temp_folder))
    rowy = 0
    for binary_image, rgb_image, num_inference_object in zip(subset_images, central_subset_rgbs, num_inference_objects):
        worksheet.write(rowy * spacing, 3, num_inference_object)
        temp_image = os.path.join(temp_folder, "temp_{}.png".format(rowy))
        cv2.imwrite(temp_image, rgb_image)
        worksheet.insert_image(
            rowy * spacing, 0, temp_image, {"x_scale": 0.3, "y_scale": 0.3}
        )
        temp_image = os.path.join(temp_folder, "temp_{}_binary.png".format(rowy))
        cv2.imwrite(temp_image, binary_image * 255)
        worksheet.insert_image(
            rowy * spacing, 1, temp_image, {"x_scale": 0.3, "y_scale": 0.3}
        )
        rowy += 1

    workbook.close()


def main():
    args = get_parser().parse_args()
    path = args.input
    min_hue = args.min_hue
    max_hue = args.max_hue
    images = glob.glob(os.path.join(path, "*." + args.image_format))
    central_subsets = []
    num_inference_objects = []
    central_subset_rgbs = []
    for image in images:
        rgb_flowcell_image = cv2.cvtColor(cv2.imread(image), cv2.COLOR_BGR2RGB)
        binary_image = binarize_by_hue_filter(rgb_flowcell_image, min_hue, max_hue)
        central_subset_rgb, central_subset, num_inference_object = count_regions_in_center_of_image(
            rgb_flowcell_image, binary_image)
        central_subsets.append(central_subset)
        central_subset_rgbs.append(central_subset_rgb)
        num_inference_objects.append(num_inference_object)

    write_xlsx(path, XLSX_SPACING, central_subsets, central_subset_rgbs, num_inference_objects)


if __name__ == '__main__':
    sys.exit(main() or 0)
