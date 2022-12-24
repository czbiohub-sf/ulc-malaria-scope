import logging
import csv
from time import perf_counter
import shutil
from typing import Dict, List, Optional
from os import mkdir, path
from datetime import datetime

import cv2
import numpy as np

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.chunker import Chunk
from ulc_mm_package.image_processing.zarrwriter import ZarrWriter
from ulc_mm_package.scope_constants import CAMERA_SELECTION
from ulc_mm_package.image_processing.processing_constants import (
    MIN_GB_REQUIRED,
    NUM_SUBSEQUENCES,
    SUBSEQUENCE_LENGTH,
    ZW_CHUNK_SIZE,
)


class DataStorageError(Exception):
    pass


class DataStorage:
    def __init__(self, default_fps: Optional[float] = None):
        self.logger = logging.getLogger(__name__)
        self.zw = ZarrWriter(chunk_size = ZW_CHUNK_SIZE)
        self.zw_chunker = Chunk(
            (CAMERA_SELECTION.IMG_HEIGHT, CAMERA_SELECTION.IMG_WIDTH),
            ZW_CHUNK_SIZE
        )
        self.write_idx = 0
        self.md_writer = None
        self.metadata_file = None
        self.main_dir = None
        self.md_keys = None
        if default_fps != None:
            self.fps = default_fps
            self.dt = 1 / self.fps
        else:
            self.dt = 0
        self.prev_write_time = 0

    def createTopLevelFolder(self, external_dir: str, datetime_str: str):
        # Create top-level directory for this program run.
        self.external_dir = external_dir
        self.main_dir = external_dir + datetime_str

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
        ext_dir: str,
        custom_experiment_name: str,
        datetime_str: str,
        experiment_initialization_metdata: Dict,
        per_image_metadata_keys: list,
    ):
        """Create the storage files for a new experiment (Zarr storage, metadata .csv files)

        Parameters
        ----------
        custom_experiment_name: str
            Appended to the end of the filename. Can also pass in an empty string ("") if no experiment name is needed.

        experiment_initialization_metadata: Dict [str : val]
            A dictionary of the experiment initialization parameters.

        per_image_metadata_keys: list [str]
            A list of the metadata keys to be stored on a per-image basis. The keys are used to create a .csv file.
        """

        if self.main_dir == None:
            self.createTopLevelFolder(ext_dir, datetime_str)

        # Create per-image metadata file
        time_str = datetime.now().strftime(DATETIME_FORMAT)
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
            self.metadata_file, fieldnames=per_image_metadata_keys
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

    def writeData(self, image: np.ndarray, metadata: Dict, count: int):
        """Write a new image and its corresponding metadata.

        Parameters
        -----------
        image: np.ndarray
            Image to be saved to the Zarr store

        metadata: Dict
            Dictionary of the per-image metadata to save. Must match the keys that were used to
            initialize the metadata file in `createNewExperiment(...)`
        """

        if self.zw.writable and perf_counter() - self.prev_write_time > self.dt:
            self.prev_write_time = perf_counter()
            maybe_chunk = self.zw_chunker.add_img(image)
            if maybe_chunk is not None:
                self.zw.threadedWriteSingleArray(maybe_chunk, self.write_idx)
                self.write_idx = count + 1
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
            path.join(self.main_dir, datetime.now().strftime(DATETIME_FORMAT))
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

        self.logger.info("Closing data storage.")
        self.save_uniform_sample()

        if self.zw.writable:
            self.zw.writable = False
            future = self.zw.threadedCloseFile()

        if self.metadata_file != None:
            self.metadata_file.close()
            self.metadata_file = None

            return future

    @classmethod
    def _get_remaining_storage_size_GB(cls, ssd_dir: str) -> float:
        """Get the remaining storage size in GB of the SSD.

        Parameters
        ----------
        path to the SSD

        Returns
        -------
        float:
            Remaining storage (GB)
        """

        return shutil.disk_usage(ssd_dir).free / 2**30  # 2^30 bytes in a gigabyte

    @classmethod
    def is_there_sufficient_storage(cls, ssd_dir: str) -> bool:
        """Check if there is sufficient storage to run an experiment.

        Parameters
        ----------
        path to the SSD

        Returns
        -------
        bool
        """

        storage_remaining_gb = cls._get_remaining_storage_size_GB(ssd_dir)
        return storage_remaining_gb > MIN_GB_REQUIRED

    def save_uniform_sample(self) -> None:
        """Extract and save a uniform random sample of images from the currently active Zarr store.

        Saves images in subsequences - i.e {N}-continuous sequences of images at {M} random locations.
        A new subfolder is created in the same folder as the experiment and images are saved as .pngs.
        """

        num_files = self.zw.array.nchunks_initialized
        try:
            indices = self._unif_subsequence_distribution(
                max_val=num_files,
                subsequence_length=SUBSEQUENCE_LENGTH,
                num_subsequences=NUM_SUBSEQUENCES,
            )
        except ValueError:
            self.logger.info("Too few images, so no subsample was generated.")
            return

        try:
            sub_seq_path = self._create_subseq_folder()
        except:
            self.logger.info(
                "Unable to create the subsample folder. Aborting subsampling."
            )
            return

        for idx in indices:
            img = self.zw.array[..., idx]
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
                dir_path = path.join(
                    self.main_dir, self.experiment_folder, "sub_sample_imgs/"
                )
                mkdir(dir_path)
                return dir_path
            except:
                # TODO
                print(f"Could not create the subsample directory")
                raise
        else:
            raise

    @staticmethod
    def _unif_subsequence_distribution(
        max_val: int, subsequence_length: int, num_subsequences: int
    ) -> List[int]:

        """Generate a set number of uniformly distributed subsequences.

        Parameters
        ----------
        max_val: int
            Maximum value of the sequence
        subsequence_length: int
            Number of samples in each subsequence
        num_subsequences: int
            Number of subsequences

        Returns
        -------
        List[int]:
            List of {num_sample} values between 0-max_val, each with at least min_dist between subsequences.
        """

        interval = np.floor((max_val - subsequence_length) / (num_subsequences - 1))
        if interval < subsequence_length:
            raise ValueError(
                f"Too few images to extract {num_subsequences} subsequences of size {subsequence_length}"
            )

        all_indices = []
        for multiple in range(0, num_subsequences):
            idx = int(multiple * interval)
            all_indices = all_indices + list(range(idx, idx + subsequence_length))

        return all_indices
