from os import mkdir, path
from datetime import datetime
import csv
from typing import Dict, List

import numpy as np

from ulc_mm_package.image_processing.zarrwriter import ZarrWriter

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
        self.main_dir = external_dir + datetime.now().strftime("%Y-%m-%d-%H%M%S")

        try:
            mkdir(self.main_dir)
        except FileNotFoundError as e:
            raise DataStorageError(f"DataStorageError - Unable to make top-level directory: {e}")

    def setMetadataKeys(self, keys: List[str]):
        self.md_keys = keys

    def createNewExperiment(self, custom_experiment_name: str, md_keys: List[str]):
        if self.main_dir == None:
            self.createTopLevelFolder()
        self.setMetadataKeys(md_keys)

        if self.metadata_file != None:
            self.metadata_file.close()
            self.metadata_file = None

        time_str = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.experiment_folder = time_str + f"_{custom_experiment_name}"

        try:
            mkdir(path.join(self.main_dir, self.experiment_folder))
        except Exception as e:
            raise DataStorage(e)

        filename = path.join(self.main_dir, self.experiment_folder, time_str) + f"_{custom_experiment_name}"
        self.metadata_file = open(f"{filename}_metadata.csv", "w")
        self.md_writer = csv.DictWriter(self.metadata_file, fieldnames=self.md_keys)
        self.md_writer.writeheader()

        self.zw.createNewFile(filename)

    def writeData(self, image: np.ndarray, metadata: Dict):
        if self.zw.writable:
            self.zw.writeSingleArray(image)
            self.md_writer.writerow(metadata)