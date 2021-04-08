import argparse
import glob
import os

from skimage.io import imread, imsave
# Program to convert gray to rgb jpg images


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-o', '--output', required=True,
        help='Output directory to save to')
    parser.add_argument(
        '-i', '--input', required=True,
        help='Input folder to convert')
    parser.add_argument(
        '-f', '--format', type=str, default=".png",
        help='Format of image')
    args = parser.parse_args()
    path = os.path.abspath(args.output)
    if not os.path.exists(path):
        os.makedirs(path)
    else:
        print("Path {} already exists, might be overwriting data".format(path))
    for input_image in glob.glob(os.path.join(args.input, "*" + args.format)):
        image = imread(input_image)
        print(os.path.basename(input_image).split(".")[0] + ".jpg")
        imsave(
            os.path.join(
                path, os.path.basename(input_image).split(".")[0] + ".jpg"),
            image)


if __name__ == '__main__':
    main()
