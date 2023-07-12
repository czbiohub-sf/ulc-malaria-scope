import io
import csv
import shutil
import logging
from pathlib import Path
from time import perf_counter
from datetime import datetime
from concurrent.futures import Future
from typing import Dict, List, Optional

import numpy as np
import numpy.typing as npt
import cv2

from ulc_mm_package.hardware.hardware_constants import DATETIME_FORMAT
from ulc_mm_package.image_processing.zarrwriter import ZarrWriter
from ulc_mm_package.image_processing.processing_constants import (
    MIN_GB_REQUIRED,
    NUM_SUBSEQUENCES,
    SUBSEQUENCE_LENGTH,
)

from ulc_mm_package.scope_constants import MAX_FRAMES


class DataStorageError(Exception):
    pass


class DataStorage:
    def __init__(self, default_fps: Optional[float] = None):
        self.logger = logging.getLogger(__name__)
        self.zw = ZarrWriter()
        self.md_writer: Optional[csv.DictWriter] = None
        self.metadata_file: Optional[io.TextIOWrapper] = None
        self.main_dir: Optional[Path] = None
        self.md_keys = None
        if default_fps is not None:
            self.fps = default_fps
            self.dt = 1 / self.fps
        else:
            self.dt = 0.0
        self.prev_write_time = 0.0

        # Calculate max number of digits, to zeropad subsample img filenames
        self.digits = int(np.log10(MAX_FRAMES - 1)) + 1

    def createTopLevelFolder(self, external_dir: str, datetime_str: str):
        # Create top-level directory for this program run.
        self.external_dir = external_dir
        self.main_dir = Path(external_dir + datetime_str)

        try:
            self.main_dir.mkdir()
        except FileNotFoundError as e:
            raise DataStorageError(f"Unable to make top-level directory: {e}")
        except PermissionError as e:
            raise DataStorageError(
                f"Unable to make top-level directory, permission issue: {e}"
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

        if self.main_dir is None:
            self.createTopLevelFolder(ext_dir, datetime_str)

        # mypy
        assert self.main_dir is not None

        # Create per-image metadata file
        self.time_str = datetime.now().strftime(DATETIME_FORMAT)
        self.experiment_folder = self.time_str + f"_{custom_experiment_name}"

        try:
            (self.main_dir / self.experiment_folder).mkdir()
        except Exception as e:
            raise DataStorageError from e

        filename = (
            self.main_dir
            / self.experiment_folder
            / f"{self.time_str}perimage_{custom_experiment_name}_metadata.csv"
        )
        self.metadata_file = open(str(filename), "w")
        self.md_writer = csv.DictWriter(
            self.metadata_file, fieldnames=per_image_metadata_keys
        )
        self.md_writer.writeheader()

        # Create experiment initialization metadata file
        exp_run_md_file = (
            self.main_dir
            / self.experiment_folder
            / f"{self.time_str}exp_{custom_experiment_name}_metadata.csv"
        )
        with open(f"{exp_run_md_file}", "w") as f:
            writer = csv.DictWriter(
                f, fieldnames=list(experiment_initialization_metdata.keys())
            )
            writer.writeheader()
            writer.writerow(experiment_initialization_metdata)

        # Create Zarr Storage
        filename = (
            self.main_dir
            / self.experiment_folder
            / f"{self.time_str}_{custom_experiment_name}"
        )
        self.zw.createNewFile(str(filename))

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
        if self.is_writable():
            assert self.md_writer is not None, "DataStorage has not been initialized"
            self.prev_write_time = perf_counter()
            self.zw.threadedWriteSingleArray(image, count)
            self.md_writer.writerow(metadata)

    def is_writable(self) -> bool:
        """Checks whether data can be written.

        Returns
        -------
        bool
        """

        return self.zw.writable and perf_counter() - self.prev_write_time > self.dt

    def writeSingleImage(self, image: np.ndarray, custom_image_name: str):
        """Save a single image w/ a custom suffix

        Parameters
        ----------
        image: np.ndarray
            Image to save as a `.png` file

        custom_image_name: str
            Name to use to save the image (appended at the end of the timestamp)
        """
        assert self.main_dir is not None, "DataStorage has not been initialized"
        filename = (
            self.main_dir
            / f"{datetime.now().strftime(DATETIME_FORMAT)}_{custom_image_name}.png"
        )
        cv2.imwrite(str(filename), image)

    def close(self, pred_tensors: List[npt.NDArray] = None) -> Optional[Future]:
        """Close the per-image metadata .csv file and Zarr image store

        Parameters
        ----------
        pred_tensors: List[npt.NDArray]
            Parsed predictions tensors from PredictionsHandler()

        Returns
        -------
        A concurrent.futures.Future object
            Can be polled to determine when the file has been successfully closed
            (future.done())
        """

        self.logger.info("Closing data storage.")
        if pred_tensors is not None:
            self.save_parsed_prediction_tensors(pred_tensors)
        self.save_uniform_sample()

        if self.metadata_file is not None:
            self.metadata_file.close()
            self.metadata_file = None

        if self.zw.writable:
            self.zw.writable = False
            future = self.zw.threadedCloseFile()

            return future

        return None

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

    def save_parsed_prediction_tensors(self, pred_tensors: npt.NDArray) -> None:
        """Save the predictions tensor (np.ndarray) containing
        the parsed prediction tensors for each image.

        The shape of this tensor is (8+NUM_CLASSES) x TOTAL_NUM_PREDICTIONS, for example if there
        are 4 classes that YOGO predicts, this array would be (12 x N).

        For details on what the indices correspond to, see `parse_prediction_tensor` in `neural_nets/utils.py`

        Parameters
        ----------
        pred_tensors: List[npt.NDArray]
            The list of parsed prediction tensors from PredictionsHandler()
        """

        assert self.main_dir is not None, "DataStorage has not been initialized"
        try:
            filename = (
                self.main_dir
                / self.experiment_folder
                / f"{self.time_str}_parsed_prediction_tensors"
            )
            np.save(filename, pred_tensors.astype(np.float32))
        except Exception as e:
            self.logger.error(f"Error saving prediction tensors. {e}")

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
            filepath = Path(sub_seq_path) / f"{idx:0{self.digits}d}.png"
            cv2.imwrite(str(filepath), img)

    def _create_subseq_folder(self) -> str:
        """Creates a folder to store the random subsample of data.

        Returns
        -------
        str:
            Path as a string
        """
        if self.zw.store is not None:
            assert self.main_dir is not None, "DataStorage has not been initialized"
            try:
                dir_path = self.main_dir / self.experiment_folder / "sub_sample_imgs"
                dir_path.mkdir()
                return str(dir_path)
            except Exception as e:
                self.logger.error(f"Could not create the subsample directory: {e}")
                raise e
        else:
            raise

    def get_experiment_path(self) -> Path:
        """
        Return path to experiment folder
        """
        assert self.main_dir is not None, "DataStorage has not been initialized"
        assert self.experiment_folder is not None, "Experiment has not been initialized"
        try:
            experiment_path = self.main_dir / self.experiment_folder
            return experiment_path
        except Exception as e:
            self.logger.error(f"Could not get experiment path: {e}")
            raise e

    def get_summary_filename(self) -> Path:
        """
        Return filename for saving statistics summary
        """
        try:
            filename = self.get_experiment_path() / f"{self.time_str}_summary.pdf"
            return filename
        except Exception as e:
            self.logger.error(f"Could not get statistics filename: {e}")
            raise e

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

        all_indices: List[int] = []
        for multiple in range(0, num_subsequences):
            idx = int(multiple * interval)
            all_indices.extend(list(range(idx, idx + subsequence_length)))

        return all_indices
