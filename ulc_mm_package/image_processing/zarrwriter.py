""" Simple Zarr storage format wrapper

-- Important Links -- 
Library Documentation:
    https://zarr.readthedocs.io/en/stable/index.html
    
"""

from os import listdir, path
from time import perf_counter
import cv2
import zarr
import numpy as np

# ==================== Custom errors ===============================
class AttemptingWriteWithoutFile(Exception):
    def __str__(self):
        return """
        No zarr file has been made and a write is being attempted.
        Ensure that 'createNewFile(filename)' has been called before attempting
        to write an array.
        """

# ==================== Main class ===============================
class ZarrWriter():
    def __init__(self):
        self.store = None
        self.group = None
        self.arr_counter = 0
        self.compressor = None
        self.writable = False

    def createNewFile(self, filename: str, metadata={}, overwrite: bool=False):
        """Create a new zarr file.
        
        Parameters
        ----------
        filename : str 
            Filename, don't include the extension (i.e pass "new_file" not "new_file.zip").
        overwrite : bool
            Will overwrite a file with the existing filename if it exists, otherwise will append.     
        """
        
        try:
            filename = f"{filename}.zip"
            if overwrite:
                self.store = zarr.ZipStore(filename, mode='x')
            else:
                self.store = zarr.ZipStore(filename, mode='w')
            self.group = zarr.group(store=self.store)
            self.arr_counter = 0
            self.writable = True
        except AttributeError:
            raise IOError(f"Error creating {filename}.zip")

    def writeSingleArray(self, data, metadata={}):
        """Write a single array and optional metadata to the Zarr store.

        Parameters
        ----------
        data : np.ndarray
        metadata : dict
            A dictionary of keys to values to be associated with the given data.
        """
        try:
            ds = self.group.array(f"{self.arr_counter}", data=data, compressor=self.compressor)
            for key in metadata.keys():
                ds.attrs[key] = metadata[key]
            self.arr_counter += 1
        except Exception:
            raise AttemptingWriteWithoutFile()

    def closeFile(self):
        self.store.close()
        self.store = None
        self.writable = False

    def __del__(self):
        # If the user did not manually close the storage, close it
        if self.store != None:
            self.store.close()

if __name__ == "__main__":
    from tqdm import tqdm

    writer = ZarrWriter()
    writer.createNewFile("experiment1")
    dir = "../raw_images_nofocus/"
    start = perf_counter()
    for img in tqdm(listdir(dir)):
        if "tif" in img:
            img = path.join(dir, img)
            arr = cv2.imread(img, 0)
            writer.writeSingleArray(arr)
    runtime = perf_counter() - start
    print(f"Num images: {len(listdir(dir))} Runtime: {runtime}")

    writer.closeFile()
