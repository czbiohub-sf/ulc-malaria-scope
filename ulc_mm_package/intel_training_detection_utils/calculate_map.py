import glob
import os
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    # Path to the folder with data, config, and weights to process
    # Example command
    # python3 calculate_map.py --data /home/vemuri/code/darknet/build/darknet/x64/data/obj.data --config yolov4-tiny-obj.cfg --weights_location backup/
    parser.add_argument("--data", help="Path to .data file used in training", type=str)
    parser.add_argument(
        "--config", help="Path to config file used to train the model", type=str
    )
    parser.add_argument(
        "--weights_location",
        help="Path to model inferred weights to calculate map for",
        type=str,
    )
    return parser


def calculate_map():
    args = get_parser().parse_args()
    weights_files = glob.glob(os.path.join(args.weights_location, "*000.weights"))
    weights_files.sort(key=os.path.getmtime)
    print(weights_files)
    for path in weights_files:
        path_without_extension = path.split(".")[0]
        command = "./darknet detector map {} {} {} > {}.map".format(
            args.data, args.config, path, path_without_extension
        )
        os.system(command)


if __name__ == "__main__":
    calculate_map()
