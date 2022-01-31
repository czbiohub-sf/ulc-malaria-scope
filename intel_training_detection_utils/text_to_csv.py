import glob
import os
import sys
from argparse import ArgumentParser

import numpy as np
import pandas as pd

LUMI_CSV_COLUMNS = ["filename", "xmin", "xmax", "ymin", "ymax", "class"]


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with model and file to process
    # Example command
    # python3 text_to_csv.py --input /Users/pranathi.vemuri/images/ --image_format .jpg --labels /Users/pranathi.vemuri/czbiohub/learn_cells/models/labels.txt
    parser.add_argument(
        "-i", "--input",
        help="Path to folder containing training, validation data",
        type=str)
    parser.add_argument(
        "--image_format",
        help="image format of training and validation images",
        type=str)
    # Labels for the neural network
    parser.add_argument(
        "--labels",
        help="Labels mapping file",
        type=str)
    parser.add_argument(
        "--images_text_path",
        help="Images text file",
        type=str)
    parser.add_argument(
        "-r", "--resolution",
        help="Resolution for the image example widthXheight",
        default='696X520', type=str)
    return parser


def convert_text_to_csv(
        input, label_names, resolution, image_format, images_text_path):
    images = glob.glob(
        os.path.join(os.path.join(input), "*" + image_format))
    images_from_text_file = open(images_text_path, "r")
    images_from_text = images_from_text_file.readlines()
    dirname = os.path.dirname(images[0])
    csv_path = os.path.join(dirname, "bb_labels.csv")
    # df = pd.DataFrame(columns=LUMI_CSV_COLUMNS)
    width, height = (int(x) for x in resolution.split('X'))
    dfs = []
    # Find boxes in each image and put them in a dataframe
    for img_name in images:
        if img_name + "\n" in images_from_text:
            basename = os.path.basename(img_name)
            text_path = os.path.join(
                dirname, basename.replace(image_format, ".txt"))
            text_file = open(text_path, "r")
            content_list = text_file.readlines()
            for line in content_list:
                # object class <x_center> <y_center> <box_width> <box_height>
                line_parts = line.split(" ")
                label_name = label_names.get(int(line_parts[0]))
                x_center = float(line_parts[1])
                y_center = float(line_parts[2])
                box_width = float(line_parts[3])
                box_height = float(line_parts[4])
                ymin = (x_center - (box_width / 2)) * width
                xmin = (y_center - (box_height / 2)) * height
                ymax = (x_center + (box_width / 2)) * width
                xmax = (y_center + (box_height / 2)) * height
                dfs.append(
                    pd.DataFrame.from_records([{
                        "filename": img_name,
                        "xmin": np.int64(xmin),
                        "xmax": np.int64(xmax),
                        "ymin": np.int64(ymin),
                        "ymax": np.int64(ymax),
                        "class": label_name
                    }])
                )
    df = pd.concat(dfs)
    df.to_csv(csv_path, index=False)


def get_label_names_for_ids(path, encoding="utf-8"):
    """Loads labels from file (with or without index numbers).

    Args:
    path: path to label file.
    encoding: label file encoding.
    Returns:
    Dictionary mapping indices to labels.
    """
    with open(path, "r", encoding=encoding) as f:
        lines = f.readlines()
        if not lines:
            return {}

    if lines[0].split(" ", maxsplit=1)[0].isdigit():
        pairs = [line.split(" ", maxsplit=1) for line in lines]
        return {int(index): label.strip() for index, label in pairs}
    else:
        return {index: line.strip() for index, line in enumerate(lines)}


def main():
    args = get_parser().parse_args()
    label_names = get_label_names_for_ids(args.labels)
    convert_text_to_csv(
        args.input, label_names, args.resolution, args.image_format, args.images_text_path)


if __name__ == '__main__':
    sys.exit(main() or 0)
