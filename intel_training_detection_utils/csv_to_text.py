import pandas as pd
import glob
import os
import sys
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with model and file to process
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
        default=None,
        type=str)
    parser.add_argument(
        "-r", "--resolution",
        help="Resolution for the image example widthXheight",
        default='696X520', type=str)
    return parser


def add_basename_gather_df(filename):
    bb_labels_df = pd.read_csv(filename)

    # Add base_path columns
    base_names = [
        os.path.basename(row["filename"])
        for index, row in bb_labels_df.iterrows()
    ]
    bb_labels_df["base_path"] = pd.Series(base_names)

    bb_labels_df.reset_index(drop=True, inplace=True)

    return bb_labels_df


def convert_csv_to_txt(
        csv_path, images, label_ids, width, height, input_image_format):
    bb_labels = add_basename_gather_df(csv_path)
    dirname = os.path.dirname(images[0])
    # Find boxes in each image and put them in a dataframe
    for img_name in images:
        # Filter out the df for all the bounding boxes in one image
        basename = os.path.basename(img_name)
        text_path = os.path.join(
            dirname, basename.replace(input_image_format, ".txt"))
        tmp_df = bb_labels[bb_labels.base_path == basename]
        # Add all the bounding boxes for the images to the dataframe
        lines = []
        for index, row in tmp_df.iterrows():
            box_width = (float(row["xmax"]) - float(row["xmin"])) + 1
            box_height = (float(row["ymax"]) - float(row["ymin"])) + 1
            scaled_box_width = box_width / width
            scaled_box_height = box_height / height
            x_center = (row["xmin"] + row["xmax"] / 2) / width
            y_center = (row["ymin"] + row["ymax"] / 2) / height
            # object class <x_center> <y_center> <box_width> <box_height>
            lines.append(
                "{} {} {} {} {}".format(label_ids.get(row['class']), x_center, y_center, scaled_box_width, scaled_box_height))
        with open(text_path, 'w') as f:
            for line in lines:
                f.write(line)
                f.write('\n')


def get_label_ids(path, encoding="utf-8"):
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
        return {label.strip(): int(index) for index, label in pairs}
    else:
        return {line.strip(): index for index, line in enumerate(lines)}


def main():
    args = get_parser().parse_args()
    label_ids = get_label_ids(args.labels)
    width, height = (int(x) for x in args.resolution.split('X'))
    train_csv_path = os.path.join(args.input, "train.csv")
    val_csv_path = os.path.join(args.input, "val.csv")
    image_format = args.image_format
    train_images = glob.glob(
        os.path.join(os.path.join(args.input, "train"), "*" + image_format))
    val_images = glob.glob(
        os.path.join(os.path.join(args.input, "val"), "*" + image_format))
    convert_csv_to_txt(
        train_csv_path, train_images, label_ids, width, height, image_format)
    convert_csv_to_txt(
        val_csv_path, val_images, label_ids, width, height, image_format)
    with open("train.txt", "w") as f:
        for image in train_images:
            f.write("data/obj/" + os.path.basename(image))
            f.write('\n')
    with open("test.txt", "w") as f:
        for image in val_images:
            f.write("data/obj/" + os.path.basename(image))
            f.write('\n')


if __name__ == '__main__':
    sys.exit(main() or 0)
