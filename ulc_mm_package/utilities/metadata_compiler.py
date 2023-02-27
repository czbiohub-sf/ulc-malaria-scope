import re
import argparse
import pandas as pd

from os import path, listdir
from ulc_mm_package.scope_constants import (
    SSD_DIR,
    SSD_NAME,
    EXPERIMENT_METADATA_KEYS,
)

DIR_KEY = "directory"
FILE_KEY = "filename"
DEFAULT_KEYS = [DIR_KEY, "notes", "git_branch"]
VALID_KEYS = [DIR_KEY, FILE_KEY] + EXPERIMENT_METADATA_KEYS

MAX_COLWIDTH = 50
TXT_FILE = "metadata_compilation.txt"


def metadata_compiler(display_keys=DEFAULT_KEYS):
    # Check that requested keys are valid
    for key in display_keys:
        if key not in VALID_KEYS:
            raise ValueError(
                "Invalid metadata column '" + key + "' requested. "
                f"Valid columns are {VALID_KEYS}"
            )

    # Get parent directory
    ssd_dir = path.join(SSD_DIR, SSD_NAME)
    if path.exists(ssd_dir):
        parent_dir = ssd_dir + "/"
    else:
        print(
            f"Could not find '{SSD_NAME}' in {SSD_DIR}. Searching for other folders in this directory."
        )
        try:
            parent_dir = SSD_DIR + listdir(SSD_DIR)[0] + "/"
        except (FileNotFoundError, IndexError):
            print(f"Could not find any folders within {SSD_DIR}.")
            return
    print(f"Getting data from {parent_dir}")

    # Get all experiment directories
    child_dirs = listdir(parent_dir)
    filtered_child_dirs = re.findall("\d{4}-\d{2}-\d{2}-\d{6}", " ".join(child_dirs))
    exp_dirs = [
        child_dir for child_dir in child_dirs if child_dir in filtered_child_dirs
    ]

    # Track dataframes from all run metadata file
    df_list = []

    # Get all run directories
    for exp_dir in exp_dirs:
        grandchild_dirs = listdir(path.join(parent_dir, exp_dir))
        filtered_grandchild_dirs = re.findall(
            "\d{4}-\d{2}-\d{2}-\d{6}_", " ".join(grandchild_dirs)
        )
        run_dirs = [
            grandchild_dir
            for grandchild_dir in grandchild_dirs
            if grandchild_dir in filtered_grandchild_dirs
        ]

        # Get run metadata file
        for run_dir in run_dirs:
            run_files = listdir(path.join(parent_dir, exp_dir, run_dir))
            filename = [run_file for run_file in run_files if "exp" in run_file][0]

            try:
                # Get data from run metadata file
                single_df = pd.read_csv(
                    path.join(parent_dir, exp_dir, run_dir, filename)
                )

                # Add file location to dataframe
                single_df[DIR_KEY] = path.join(exp_dir, run_dir)
                single_df[FILE_KEY] = filename

                df_list.append(single_df)
            except pd.errors.EmptyDataError:
                print(f"Empty file: {path.join(exp_dir, run_dir, filename)}")

    master_df = pd.concat(df_list, ignore_index=True)
    master_df = master_df.sort_values(by="directory", ignore_index=True)
    master_df = master_df.fillna("-")

    # Truncate notes columns for readability
    truncated_master_df = master_df.copy()
    truncated_master_df["notes"] = [
        note[: MAX_COLWIDTH - 3] + "..." if len(note) > MAX_COLWIDTH - 3 else note
        for note in master_df["notes"]
    ]

    print("\n" + truncated_master_df[display_keys].to_string())

    with open(TXT_FILE, "w") as writer:
        writer.write(master_df[display_keys].to_string())
    print(f"\nWrote untruncated metadata compilation to {TXT_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Metadata compiler",
        description=f"By default, only the columns {DEFAULT_KEYS} are displayed. Additional columns can be viewed using the flags below.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        help="display all experiment metadata columns",
        action="store_true",
    )
    parser.add_argument(
        "-i",
        "--include",
        dest="key",
        help=f"include the specified column in the displayed metadata, any of {VALID_KEYS} can be specified",
        action="store",
    )
    args = parser.parse_args()

    if args.verbose:
        metadata_compiler(display_keys=VALID_KEYS)
    elif args.key is not None:
        custom_keys = DEFAULT_KEYS + [args.key]
        metadata_compiler(display_keys=custom_keys)
    else:
        metadata_compiler()
