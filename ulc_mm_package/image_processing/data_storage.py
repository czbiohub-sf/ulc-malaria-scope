from os import mkdir, path, listdir
from datetime import datetime
import csv
import random
from typing import Dict, List
import shutil

import numpy as np
import cv2

from ulc_mm_package.scope_constants import DEFAULT_SSD
from ulc_mm_package.image_processing.zarrwriter import ZarrWriter
from ulc_mm_package.image_processing.processing_constants import (
    MIN_GB_REQUIRED,
    NUM_SUBSEQUENCE,
    SUBSEQUENCE_LENGTH,
)


class DataStorageError(Exception):
    pass


class DataStorage:
    def __init__(self):
        self.zw = ZarrWriter()
        self.md_writer = None
        self.metadata_file = None
        self.main_dir = None
        self.md_keys = None

    def createTopLevelFolder(self, external_dir: str):
        # Create top-level directory for this program run.
        self.external_dir = external_dir
        self.main_dir = external_dir + datetime.now().strftime("%Y-%m-%d-%H%M%S")

        try:
            mkdir(self.main_dir)
        except FileNotFoundError as e:
            raise DataStorageError(
                f"DataStorageError - Unable to make top-level directory: {e}"
            )
        except PermissionError as e:
            raise DataStorage(
                f"DataStorageError - Unable to make top-level directory, permission issue: {e}"
            )

    def createNewExperiment(
        self,
        custom_experiment_name: str,
        experiment_initialization_metdata: Dict,
        per_image_metadata: Dict,
    ):
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

        filename = (
            path.join(self.main_dir, self.experiment_folder, time_str)
            + f"perimage_{custom_experiment_name}_metadata.csv"
        )
        self.metadata_file = open(f"{filename}", "w")
        self.md_writer = csv.DictWriter(
            self.metadata_file, fieldnames=list(per_image_metadata.keys())
        )
        self.md_writer.writeheader()

        # Create experiment initialization metadata file
        exp_run_md_file = (
            path.join(self.main_dir, self.experiment_folder, time_str)
            + f"exp_{custom_experiment_name}_metadata.csv"
        )
        with open(f"{exp_run_md_file}", "w") as f:
            writer = csv.DictWriter(
                f, fieldnames=list(experiment_initialization_metdata.keys())
            )
            writer.writeheader()
            writer.writerow(experiment_initialization_metdata)

        # Create Zarr Storage
        filename = (
            path.join(self.main_dir, self.experiment_folder, time_str)
            + f"_{custom_experiment_name}"
        )
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
            self.zw.threadedWriteSingleArray(image)
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
        """Close the per-image metadata .csv file and Zarr image store

        Returns
        -------
        A concurrent.futures.Future object
            Can be polled to determine when the file has been successfully closed
            (future.done())
        """

        if self.metadata_file != None:
            self.metadata_file.close()
            self.metadata_file = None

        if self.zw.writable:
            return self.zw.threadedCloseFile()

    def _get_remaining_storage_size_GB(self) -> float:
        """Get the remaining storage size in GB of the SSD.

        Returns
        -------
        float:
            Remaining storage (GB)
        """

        return (
            shutil.disk_usage(self.external_dir).free / 2**30
        )  # 2^30 bytes in a gigabyte

    def is_there_sufficient_storage(self) -> bool:
        """Check if there is sufficient storage to run an experiment.

        Returns
        -------
        bool
        """

        storage_remaining_gb = self._get_remaining_storage_size_GB()
        return storage_remaining_gb > MIN_GB_REQUIRED

    def save_uniform_random_sample(self) -> None:
        """Extract and save a uniform random sample of images from the currently active Zarr store.

        Saves images in subsequences - i.e {N}-continuous sequences of images at {M} random locations.
        A new subfolder is created in the same folder as the experiment and images are saved as .pngs.
        """

        num_files = len(self.zw.group)
        indices = self._unif_rand_with_min_distance(
            max_val=num_files, num_samples=NUM_SUBSEQUENCE, min_dist=SUBSEQUENCE_LENGTH
        )

        try:
            sub_seq_path = self._create_subseq_folder()
        except:
            # TODO: change to logging
            print("Unable to create the subsample folder - aborting subsampling.")
            return

        for idx in indices:
            img = self.zw.group[idx][:]
            filepath = path.join(sub_seq_path, f"{idx}.png")
            cv2.imwrite(filepath, img)

    def _create_subseq_folder(self) -> str:
        """Creates a folder to store the random subsample of data.

        Returns
        -------
        str:
            Path as a string
        """

        if self.zw.store != None:
            try:
                dir_path = path.join(self.main_dir, "sub_sample_imgs/")
                mkdir(dir_path)
                return dir_path
            except:
                # TODO
                print(f"Could not create the subsample directory")
                raise
        else:
            raise

    @staticmethod
    def _unif_rand_with_min_distance(
        max_val: int, num_samples: int, min_dist: int
    ) -> List[int]:

        """Generate a uniform distributed random sample with a minimum distance between samples.

        Parameters
        ----------
        max_val: int
            Maximum value of the sequence
        num_samples; int
            Number of samples to return
        min_dist: int
            Minimum distance between returned samples

        Returns
        -------
        List[int]:
            List of {num_sample} values between 0-max_val, each with at least min_dist between them.
        """

        return [
            (min_dist - 1) * i + val
            for i, val in enumerate(
                sorted(
                    random.sample(
                        range(max_val - (min_dist - 1) * num_samples), num_samples
                    )
                )
            )
        ]
