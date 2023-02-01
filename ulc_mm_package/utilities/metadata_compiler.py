import re
import pandas as pd

from os import path, listdir
from ulc_mm_package.scope_constants import (
    SSD_DIR,
    SSD_NAME,
    EXPERIMENT_METADATA_KEYS,
)

DIR_KEY = "directory"

def metadata_compiler(display_keys = [DIR_KEY, 'notes', 'git_branch', 'git_commit']):

    # Check that requested keys are valid
    valid_keys = EXPERIMENT_METADATA_KEYS + [DIR_KEY]
    print(valid_keys)
    for key in display_keys:
        if not key in valid_keys:
            raise ValueError(f"Invalid metadata key: {key}")

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
        except (FileNotFoundError, IndexError) as e:
            print(
                f"Could not find any folders within {SSD_DIR}."
            )
            return
    print(f"Getting data from {parent_dir}")

    # Get all experiment directories
    child_dirs = listdir(parent_dir)
    filtered_child_dirs = re.findall("\d{4}-\d{2}-\d{2}-\d{6}", " ".join(child_dirs))

    exp_dirs = [child_dir for child_dir in child_dirs if child_dir in filtered_child_dirs]

    # Track dataframes from all run metadata file
    df_list = []

    # Get all run directories
    for exp_dir in exp_dirs:
        run_dirs = listdir(path.join(parent_dir, exp_dir))
        
        # Get run metadata file
        for run_dir in run_dirs:
            run_files = listdir(path.join(parent_dir, exp_dir, run_dir))
            filename = [run_file for run_file in run_files if "exp" in run_file][0]

            # Get data from run metadata file
            run_df = pd.read_csv(path.join(parent_dir, exp_dir, run_dir, filename))

            # Add file location to dataframe
            run_df[DIR_KEY] = path.join(exp_dir, run_dir)

            df_list.append(run_df)

    df_compilation = pd.concat(df_list, ignore_index=True)
    print(df_compilation['directory'].to_string())


                

    # Get metadata from all runs

    

if __name__ == "__main__":
    'directory'
    metadata_compiler(display_keys=EXPERIMENT_METADATA_KEYS)

    # TODO add optional arguments
