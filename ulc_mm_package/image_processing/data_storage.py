from os import mkdir, path, listdir
from datetime import datetime
import csv
from typing import Dict, List

import numpy as np
import cv2

from ulc_mm_package.image_processing.zarrwriter import ZarrWriter
from ulc_mm_package.image_processing.processing_constants import EXPERIMENT_METADATA_KEYS, PER_IMAGE_METADATA_KEYS

class DataStorageError(Exception):
    pass

DEFAULT_SSD = "/media/pi/"

class DataStorage:
    def __init__(self):
        self.zw = ZarrWriter()
        self.md_writer = None
        self.metadata_file = None
        self.main_dir = None
        self.md_keys = None

    def createTopLevelFolder(self, external_dir: str):
        # Create top-level directory for this program run.
        self.main_dir = external_dir + datetime.now().strftime("%Y-%m-%d-%H%M%S")

        try:
            mkdir(self.main_dir)
        except FileNotFoundError as e:
            raise DataStorageError(f"DataStorageError - Unable to make top-level directory: {e}")

    def createNewExperiment(self, custom_experiment_name: str, experiment_initialization_metdata: Dict, per_image_metadata: Dict, main_dir):
        """Create the storage files for a new experiment (Zarr storage, metadata .csv files)

        Parameters
        ----------
        custom_experiment_name: str
            Appended to the end of the filename. Can also pass in an empty string ("") if no experiment name is needed.

        experiment_initialization_metadata: Dict [str : val]
            A dictionary of the experiment initialization parameters.

        per_image_metadata: Dict [str : val]
            A dictionary of the metadata to be stored on a per-image basis. Since this is just for initialization,
            the dictionary does not necessarily need to have any values - this function just needs to keys in order to
            create the `.csv` file.
        """

        if self.main_dir == None:
            media_dir = DEFAULT_SSD
            external_dir = media_dir + listdir(media_dir)[0] + "/"
            self.createTopLevelFolder(external_dir)

        # Create per-image metadata file
        time_str = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.experiment_folder = time_str + f"_{custom_experiment_name}"

        try:
            mkdir(path.join(self.main_dir, self.experiment_folder))
        except Exception as e:
            raise DataStorage(e)

        filename = path.join(self.main_dir, self.experiment_folder, time_str) + f"perimage_{custom_experiment_name}_metadata.csv"
        self.metadata_file = open(f"{filename}", "w")
        self.md_writer = csv.DictWriter(self.metadata_file, fieldnames=list(per_image_metadata.keys()))
        self.md_writer.writeheader()

        # Create experiment initialization metadata file
        exp_run_md_file = path.join(self.main_dir, self.experiment_folder, time_str) + f"exp_{custom_experiment_name}_metadata.csv"
        with open(f"{exp_run_md_file}", "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(experiment_initialization_metdata.keys()))
            writer.writeheader()
            writer.writerow(experiment_initialization_metdata)

        # Create Zarr Storage
        self.zw.createNewFile(filename)

    def writeData(self, image: np.ndarray, metadata: Dict):
        """Write a new image and its corresponding metadata.

        Paramaeters
        -----------
        image: np.ndarray
            Image to be saved to the Zarr store

        metadata: Dict
            Dictionary of the per-image metadata to save. Must match the keys that were used to
            initialize the metadata file in `createNewExperiment(...)`
        """

        if self.zw.writable:
            self.zw.writeSingleArray(image)
            self.md_writer.writerow(metadata)

    def writeSingleImage(self, image: np.ndarray, custom_image_name: str):
        """Save a single image w/ a custom suffix

        Parameters
        ----------
        image: np.ndarray
            Image to save as a `.png` file

        custom_image_name: str
            Name to use to save the image (appended at the end of the timestamp)
        """

        filename = (
                path.join(self.main_dir, datetime.now().strftime("%Y-%m-%d-%H%M%S"))
                + f"_{custom_image_name}.png"
            )
        cv2.imwrite(filename, image)

    def close(self):
        """Close the per-image metadata .csv file and Zarr image store"""

        if self.metadata_file != None:
            self.metadata_file.close()
            self.metadata_file = None

        if self.zw.writable:
            self.zw.closeFile()