import io
import csv
import shutil
import logging
from os import remove
from pathlib import Path
from time import perf_counter
from datetime import datetime
from concurrent.futures import Future
from typing import Dict, List, Optional
from stats_utils.compensator import CountCompensator

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
from ulc_mm_package.neural_nets.utils import (
    get_class_counts,
    save_thumbnails_to_disk,
)
from ulc_mm_package.neural_nets.neural_network_constants import (
    ASEXUAL_PARASITE_CLASS_IDS,
    YOGO_CLASS_LIST,
    YOGO_MODEL,
)

from ulc_mm_package.scope_constants import (
    MAX_FRAMES,
    RBCS_PER_UL,
    SUMMARY_REPORT_CSS_FILE,
    DESKTOP_SUMMARY_DIR,
    DESKTOP_CELL_COUNT_DIR,
    CSS_FILE_NAME,
    DEBUG_REPORT,
)
from ulc_mm_package.summary_report.make_summary_report import (
    make_html_report,
    make_per_image_metadata_plots,
    make_cell_count_plot,
    make_yogo_conf_plots,
    make_yogo_objectness_plots,
    save_html_report,
    create_pdf_from_html,
)


class DataStorageError(Exception):
    pass


def write_img(img: np.ndarray, filepath: Path):
    """Write an image to disk

    img: np.ndarray
    filepath: Path
    """

    cv2.imwrite(str(filepath), img)


class DataStorage:
    def __init__(self, stats_utils, default_fps: Optional[float] = None):
        self.logger = logging.getLogger(__name__)
        self.stats_utils = None
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

    def initCountCompensator(self, clinical):
        self.compensator = CountCompensator(YOGO_MODEL, clinical=clinical)

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
        experiment_initialization_metadata: Dict,
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

        # Keep experiment metadata
        self.experiment_level_metadata = experiment_initialization_metadata

        try:
            (self.main_dir / self.experiment_folder).mkdir()
        except Exception as e:
            raise DataStorageError from e

        filename = (
            self.main_dir
            / self.experiment_folder
            / f"{self.time_str}perimage_{custom_experiment_name}_metadata.csv"
        )
        self.per_img_metadata_filename = filename
        self.metadata_file = open(str(self.per_img_metadata_filename), "w")
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
                f, fieldnames=list(experiment_initialization_metadata.keys())
            )
            writer.writeheader()
            writer.writerow(experiment_initialization_metadata)

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

    def close(
        self,
        pred_tensors: Optional[npt.NDArray] = None,
        heatmap: Optional[npt.NDArray] = None,
    ) -> Optional[Future]:
        """Close the per-image metadata .csv file and Zarr image store

        Parameters
        ----------
        pred_tensors: Optional[npt.NDArray]
            Parsed predictions tensors from PredictionsHandler()
        heatmap: Optional[npt.NDArray]
            Heatmap from PredictionsHandler()

        Returns
        -------
        A concurrent.futures.Future object
            Can be polled to determine when the file has been successfully closed
            (future.done())
        """

        self.logger.info(f"{'='*10}Closing data storage.{'='*10}")

        self.logger.info("> Saving subsample images...")
        self.save_uniform_sample()

        self.logger.info("> Closing metadata file...")
        if self.metadata_file is not None:
            self.metadata_file.close()
            self.metadata_file = None

        if pred_tensors is not None and pred_tensors.size > 0:
            self.logger.info("> Saving prediction tensors...")
            self.save_npy_arr("parsed_prediction_tensors", pred_tensors)

            if heatmap is not None:
                self.logger.info("> Saving heatmap array...")
                self.save_npy_arr("heatmap", heatmap)

            self.logger.info(
                "> Saving subset of healthy and parasite thumbnails to disk..."
            )
            class_to_thumbnails_path: Dict[str, Path] = save_thumbnails_to_disk(
                self.zw.array, pred_tensors, self.get_experiment_path()
            )

            ### Create summary report
            self.logger.info("> Creating summary report...")
            summary_report_dir = self.get_experiment_path() / "summary_report"
            Path.mkdir(summary_report_dir, exist_ok=True)

            ### NOTE: xhtml2pdf fails if you provide relative image file paths, e.g ("../thumbnails/ring/1.png")
            ### so provide absolute filepaths only. Note this means that the html file will be broken if viewed from anywhere other than the Pi.

            class_to_all_thumbnails_abs_path: Dict[str, List[str]] = {
                x: [
                    str(y.resolve())
                    for y in list(class_to_thumbnails_path[x].rglob("*.png"))
                ]
                for x in class_to_thumbnails_path.keys()
            }

            html_abs_path_temp_loc = (
                summary_report_dir / f"{self.time_str}_temp_summary.html"
            )
            pdf_save_loc = summary_report_dir / f"{self.time_str}_summary.pdf"

            # Create per-image metadata plot
            per_image_metadata_plot_save_loc = str(
                summary_report_dir / f"{self.time_str}_per_image_metadata_plot.jpg"
            )

            per_img_metadata_file = open(self.per_img_metadata_filename, "r")
            counts_plot_loc = str(summary_report_dir / "counts.jpg")
            conf_plot_loc = str(summary_report_dir / "confs.jpg")
            objectness_plot_loc = str(summary_report_dir / "objectness.jpg")

            # Only generate additional plots if DEBUG_REPORT environment variable is set to True
            if DEBUG_REPORT:
                make_per_image_metadata_plots(
                    per_img_metadata_file, per_image_metadata_plot_save_loc
                )

                try:
                    make_cell_count_plot(pred_tensors, counts_plot_loc)
                except Exception as e:
                    self.logger.error(f"Failed to make cell count plot - {e}")
                try:
                    make_yogo_conf_plots(pred_tensors, conf_plot_loc)
                except Exception as e:
                    self.logger.error(f"Failed to make yogo confidence plots - {e}")
                try:
                    make_yogo_objectness_plots(pred_tensors, objectness_plot_loc)
                except Exception as e:
                    self.logger.error(f"Failed to make yogo objectness plots - {e}")

            # Get cell counts
            raw_cell_counts = get_class_counts(pred_tensors)
            # Associate class with counts
            class_name_to_cell_count = {
                x.capitalize(): y for (x, y) in zip(YOGO_CLASS_LIST, raw_cell_counts)
            }
            # 'parasites per ul' is # of rings / total rbcs * scaling factor (RBCS_PER_UL)
            perc_parasitemia, perc_parasitemia_err = (
                self.compensator.get_res_from_counts(raw_cell_counts)
            )

            perc_parasitemia = f"{perc_parasitemia:.1f}"
            perc_parasitemia_err = f"{perc_parasitemia_err:.1f}"

            parasites_per_ul = f"{RBCS_PER_UL*perc_parasitemia:.1f}"
            parasitemia_per_ul_err = f"{RBCS_PER_UL*perc_parasitemia_err:.1f}"

            # HTML w/ absolute path
            abs_css_file_path = str((summary_report_dir / CSS_FILE_NAME).resolve())
            html_report_with_abs_path = make_html_report(
                self.time_str,
                self.experiment_level_metadata,
                per_image_metadata_plot_save_loc,
                max(1, total_rbcs),  # Account for potential div-by-zero
                class_name_to_cell_count,
                perc_parasitemia,
                perc_parasitemia_err,
                parasites_per_ul,
                parasites_per_ul_err,
                class_to_all_thumbnails_abs_path,
                counts_plot_loc,
                conf_plot_loc,
                objectness_plot_loc,
                css_path=abs_css_file_path,
            )

            # Copy the CSS file to the summary directory
            shutil.copy(SUMMARY_REPORT_CSS_FILE, summary_report_dir)

            # Save the temporary HTML file w/ absolute path so we can properly generate the PDF
            save_html_report(html_report_with_abs_path, html_abs_path_temp_loc)
            create_pdf_from_html(html_abs_path_temp_loc, pdf_save_loc)

            # Make a copy of the summary PDF to the Desktop
            shutil.copy(pdf_save_loc, DESKTOP_SUMMARY_DIR)

            # Remove intermediate files
            remove(html_abs_path_temp_loc)
            remove(summary_report_dir / CSS_FILE_NAME)

            if DEBUG_REPORT:
                remove(counts_plot_loc)
                remove(per_image_metadata_plot_save_loc)
                remove(conf_plot_loc)
                remove(objectness_plot_loc)

            # Write to a separate csv with just cell counts for each class
            self.logger.info("Writing cell counts to csv...")
            cell_count_loc = (
                self.get_experiment_path() / f"{self.time_str}_cell_counts.csv"
            )
            with open(f"{cell_count_loc}", "w") as f:
                writer = csv.writer(f)
                writer.writerow(class_name_to_cell_count.keys())
                writer.writerow(class_name_to_cell_count.values())
            shutil.copy(cell_count_loc, DESKTOP_CELL_COUNT_DIR)

        self.logger.info("> Closing zarr image store...")
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

    def save_npy_arr(self, fn: str, arr: npt.NDArray) -> None:
        """Save the given numpy array with the given filename.
        The datetime string will be prepended automatically to the filename.

        Parameters
        ----------
        filename: str
        arr: npt.NDArray
            The numpy array to save
        """

        assert self.main_dir is not None, "DataStorage has not been initialized"
        try:
            filename = self.main_dir / self.experiment_folder / f"{self.time_str}_{fn}"
            np.save(filename, arr.astype(np.float32))
        except Exception as e:
            self.logger.error(f"Error saving {filename}: {e}")

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
            img_path = Path(sub_seq_path) / f"{idx:0{self.digits}d}.png"
            write_img(img, img_path)

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
