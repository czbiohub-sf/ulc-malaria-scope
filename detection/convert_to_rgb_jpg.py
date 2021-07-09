import argparse
import glob
import os

import cv2
from skimage.io import imread, imsave
from skimage.transform import resize
import numpy as np

# Program to convert gray to rgb jpg images


def scale_to_uint8(image):
    return ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)


def skimage_resize(image, height, width):
    if len(image.shape) == 3:
        return scale_to_uint8(
            resize(image, (height, width, image.shape[2]), order=3, preserve_range=True)
        )
    else:
        return scale_to_uint8(
            resize(image, (height, width), order=3, preserve_range=True)
        )


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-o", "--output", required=True, help="Output directory to save to"
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Input folder or file to convert"
    )
    parser.add_argument(
        "-f", "--format", type=str, default=".png", help="Format of image"
    )
    parser.add_argument(
        "--resize", type=int, nargs="+", required=False, help="Resize image to a shape"
    )
    args = parser.parse_args()
    path = os.path.abspath(args.output)
    if not os.path.exists(path):
        os.makedirs(path)
    else:
        print("Path {} already exists, might be overwriting data".format(path))

    input_path = args.input
    format_of_files = args.format
    input_images = []
    if input_path.endswith(format_of_files):
        input_images.append(input_path)
    else:
        for input_image in glob.glob(os.path.join(input_path, "*" + format_of_files)):
            input_images.append(input_image)
    for input_image in input_images:
        image = imread(input_image)
        if image.dtype != np.uint8:
            image = scale_to_uint8(image)
        if args.resize:
            shape = tuple(args.resize)
            image = skimage_resize(image, shape[0], shape[1])
        if len(image.shape) == 3:
            if image.shape[2] == 1:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        imsave(
            os.path.join(path, os.path.basename(input_image).split(".")[0] + ".jpg"),
            image,
        )


if __name__ == "__main__":
    main()
