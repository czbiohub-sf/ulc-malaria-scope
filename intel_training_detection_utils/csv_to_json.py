import csv
import glob
import json
import os
import sys
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with model and file to process
    # Example command
    # python3 csv_to_json.py --input /Users/pranathi.vemuri/images/ --image_format jpg --labels /Users/pranathi.vemuri/czbiohub/learn_cells/models/labels.txt
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


def get_labels_dict(path, encoding="utf-8"):
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
        return [
            {"id": int(index) + 1,
             "supercategory": "",
             "name": label.strip()} for index, label in pairs]
    else:
        return [
            {"id": index + 1,
             "supercategory": "",
             "name": line.strip()} for index, line in enumerate(lines)]


def convert_csv_to_json(
        csv_path, labels, images, label_ids, image_ids):
    json_path = csv_path.replace(".csv", ".json")
    annotations = []
    with open(csv_path, "r") as f:
        reader = csv.reader(f, delimiter="\t")
        for i, line in enumerate(reader):
            line = line[0].split(",")
            if i > 0:
                width = (float(line[2]) - float(line[1])) + 1
                height = (float(line[4]) - float(line[3])) + 1
                annotations.append(
                    {"category_id": label_ids.get(line[5]) + 1,
                     "segmentation": None,
                     "bbox": [
                        float(line[1]), float(line[3]), width, height],
                     "iscrowd": 0,
                     "area": width * height,
                     "id": 0,
                     "image_id": image_ids.get(line[0]),
                     "attributes": {},
                     "is_occluded": False})
    data = {"categories": labels, "images": images, "annotations": annotations}
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


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


def get_images_dict(path, image_format, subfolder, width, height):
    images = glob.glob(os.path.join(path, "*." + image_format))
    image_ids = {image: index for index, image in enumerate(images)}
    images_dict = []
    for image in images:
        basename = os.path.basename(image)
        images_dict.append(
            {"date_captured": None,
             "flickr_url": None,
             "width": width,
             "dataset": "ULC_dataset",
             "file_name": basename,
             "license": None,
             "image": subfolder + os.sep + basename,
             "id": image_ids.get(image),
             "height": height,
             "coco_url": None})
    return images_dict, image_ids


def main():
    args = get_parser().parse_args()
    labels = get_labels_dict(args.labels)
    label_ids = get_label_ids(args.labels)
    width, height = (int(x) for x in args.resolution.split('X'))
    train_images, train_image_ids = get_images_dict(
        os.path.join(args.input, "train"),
        args.image_format, "train", width, height)
    val_images, val_image_ids = get_images_dict(
        os.path.join(args.input, "val"),
        args.image_format, "val", width, height)
    train_csv_path = os.path.join(args.input, "train.csv")
    val_csv_path = os.path.join(args.input, "val.csv")
    convert_csv_to_json(
        train_csv_path, labels, train_images, label_ids, train_image_ids)
    convert_csv_to_json(
        val_csv_path, labels, val_images, label_ids, val_image_ids)


if __name__ == '__main__':
    sys.exit(main() or 0)
