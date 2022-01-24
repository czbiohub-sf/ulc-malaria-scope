import glob
import os
import sys
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    # Write a text file with image paths for inferencing
    # Example command
    # python3 make_images_text_file.py --input /mnt/data_lg/pranathi/bioengineering_data/uv_multi_color/random_mosaic_sick/ --image_format .tif --output_text_path new_train.txt
    parser.add_argument(
        "-i", "--input",
        help="Path to folder containing images to write to the text file",
        type=str)
    parser.add_argument(
        "--image_format",
        help="image format of images, including .",
        type=str)
    parser.add_argument(
        "--output_text_path",
        help="output text file",
        type=str)
    return parser


def main():
    args = get_parser().parse_args()
    images = glob.glob(
        os.path.join(os.path.join(args.input), "*" + args.image_format))
    with open(args.output_text_path, "w") as f:
        for image in images:
            f.write(image)
            f.write('\n')


if __name__ == '__main__':
    sys.exit(main() or 0)
