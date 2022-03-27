import glob
import fiftyone as fo
import pandas as pd
import os
import sys
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with model and file to process
    # Example command
    # python3 csv_to_json.py --input /Users/pranathi.vemuri/images/ --image_format jpg --labels /Users/pranathi.vemuri/czbiohub/learn_cells/models/labels.txt
    parser.add_argument(
        "-i",
        "--input",
        help="Path to folder containing training, validation data",
        type=str,
    )
    parser.add_argument(
        "--image_format",
        help="image format of training and validation images",
        type=str,
    )
    # Labels for the neural network
    parser.add_argument("--labels", help="Labels mapping file", default=None, type=str)
    parser.add_argument(
        "-r",
        "--resolution",
        help="Resolution for the image example widthXheight",
        default="696X520",
        type=str,
    )
    return parser


def add_basename_gather_df(filename):
    bb_labels_df = pd.read_csv(filename)

    # Add base_path columns
    base_names = [
        os.path.basename(row["filename"]) for index, row in bb_labels_df.iterrows()
    ]
    bb_labels_df["base_path"] = pd.Series(base_names)

    bb_labels_df.reset_index(drop=True, inplace=True)

    return bb_labels_df


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
            {"id": int(index) + 1, "supercategory": "", "name": label.strip()}
            for index, label in pairs
        ]
    else:
        return [
            {"id": index + 1, "supercategory": "", "name": line.strip()}
            for index, line in enumerate(lines)
        ]


def main():
    args = get_parser().parse_args()
    label_ids = get_label_ids(args.labels)
    images = glob.glob(os.path.join(args.input, "*." + args.image_format))
    bb_labels = add_basename_gather_df(os.path.join(args.input, "train.csv"))

    # Create dataset
    dataset = fo.Dataset(name="rbc-malaria")

    # Persist the dataset on disk in order to
    # be able to load it in one line in the future
    dataset.persistent = True
    image_width, image_height = (int(x) for x in args.resolution.split("X"))

    for img_name in images:
        # Filter out the df for all the bounding boxes in one image
        basename = os.path.basename(img_name)
        tmp_df = bb_labels[bb_labels.base_path == basename]
        # Add all the bounding boxes for the images to the dataframe
        # Convert detections to FiftyOne format
        sample = fo.Sample(filepath=img_name)
        detections = []
        for index, row in tmp_df.iterrows():
            label = label_ids.get(row["class"]) + 1

            # Bounding box coordinates should be relative values
            # in [0, 1] in the following format:
            # [top-left-x, top-left-y, width, height]
            width = ((float(row["xmax"]) - float(row["xmin"])) + 1) / image_width
            height = ((float(row["ymax"]) - float(row["ymin"])) + 1) / image_height
            xmin = row["xmin"] / image_width
            ymin = row["ymin"] / image_width

            detections.append(
                fo.Detection(label=label, bounding_box=[xmin, ymin, width, height])
            )

        # Store detections in a field name of your choice
        sample["ground_truth"] = fo.Detections(detections=detections)

        dataset.add_sample(sample)

    export_dir = "coco_rbc"
    print(export_dir)
    label_field = ["healthy", "ring", "schizont", "troph"]  # for example

    # Export the dataset
    dataset.export(
        export_dir=export_dir,
        dataset_type=fo.types.COCODetectionDataset,
        label_field=label_field,
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
