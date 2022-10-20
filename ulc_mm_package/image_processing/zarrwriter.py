f""" Simple Zarr storage format wrapper

-- Important Links -- 
Library Documentation:
    https://zarr.readthedocs.io/en/stable/index.html
    
"""

import functools
import threading
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from time import perf_counter
import zarr


WRITE_LOCK = threading.Lock()


def lockNoBlock(lock):
    def lockDecorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not lock.locked():
                with lock:
                    return func(*args, **kwargs)
            else:
                raise WriteInProgress

        return wrapper

    return lockDecorator


# ==================== Custom errors ===============================
class AttemptingWriteWithoutFile(Exception):
    def __str__(self):
        return """
        No zarr file has been made and a write is being attempted.
        Ensure that 'createNewFile(filename)' has been called before attempting
        to write an array.
        """


class WriteInProgress(Exception):
    def __str__(self):
        return "Write in progress."


# ==================== Main class ===============================
class ZarrWriter:
    def __init__(self):
        self.store = None
        self.group = None
        self.arr_counter = 0
        self.compressor = None
        self.writable = False
        self.prev_write_time = 0
        self.futures = []
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.fps = 30
        self.dt = 1 / self.fps

    def createNewFile(self, filename: str, metadata={}, overwrite: bool = False):
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
                self.store = zarr.ZipStore(filename, mode="x")
            else:
                self.store = zarr.ZipStore(filename, mode="w")
            self.group = zarr.group(store=self.store)
            self.arr_counter = 0
            self.writable = True
        except AttributeError:
            raise IOError(f"Error creating {filename}.zip")

    @lockNoBlock(WRITE_LOCK)
    def writeSingleArray(self, data):
        """Write a single array and optional metadata to the Zarr store.

        Parameters
        ----------
        data : np.ndarray
        metadata : dict
            A dictionary of keys to values to be associated with the given data.
        """

        # Rate-limit writing to disk to `self.fps``
        if perf_counter() - self.prev_write_time < self.dt:
            return

        try:
            ds = self.group.array(
                f"{self.arr_counter}", data=data, compressor=self.compressor
            )
            self.arr_counter += 1
            self.prev_write_time = perf_counter()
            return self.arr_counter
        except Exception:
            raise AttemptingWriteWithoutFile()

    def threadedWriteSingleArray(self, *args, **kwargs):
        self.futures.append(self.executor.submit(self.writeSingleArray, *args))

    @lockNoBlock(WRITE_LOCK)
    def closeFile(self):
        """Close the Zarr store."""
        self.writable = False
        wait(self.futures, return_when=ALL_COMPLETED)
        self.store.close()
        self.store = None
        self.futures = []

    def threadedCloseFile(self):
        """Close the file in a separate thread (and locks the ability to write to the file).

        This threaded close was written with UI.py in mind, so that the file can be closed while 
        keeping the rest of the GUI responsive.
        
        Returns
        -------
        future: An object that can be polled to check if closing the file has completed
        """
        return self.executor.submit(self.closeFile)

    def __del__(self):
        # If the user did not manually close the storage, close it
        if self.store != None:
            self.store.close()