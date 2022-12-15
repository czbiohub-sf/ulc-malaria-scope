f""" Simple Zarr storage format wrapper

-- Important Links --
Library Documentation:
    https://zarr.readthedocs.io/en/stable/index.html

"""

import functools
import threading
from time import perf_counter
import logging
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait

import zarr
import threading

from time import perf_counter
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait

from ulc_mm_package.utilities.lock_utils import lock_no_block


WRITE_LOCK = threading.Lock()


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
        self.writable = False
        self.futures = []
        self.futures_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=16)
        self.logger = logging.getLogger(__name__)

    def createNewFile(self, filename: str, overwrite: bool = False):
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
            self.array = zarr.open(
                filename,
                "x" if overwrite else "w",
                shape=(772, 1032, int(2e9)),
                chunks=(772, 1032, 1),
                compressor=None,
                dtype="u1",
            )
            self.writable = True
        except AttributeError as e:
            self.logger.error(
                f"zarrwriter.py : createNewFile : Exception encountered - {e}"
            )
            raise IOError(f"Error creating {filename}.zip")

    def writeSingleArray(self, data, pos: int) -> None:
        """Write a single array and optional metadata to the Zarr store.

        Parameters
        ----------
        data : np.ndarray - the image to write
        pos: int - the index of the zarr array to write to

        Since each `pos` is a different chunk, it is threadsafe - see
        https://zarr.readthedocs.io/en/stable/tutorial.html#parallel-computing-and-synchronization
        """
        try:
            self.array[:, :, pos] = data
        except Exception as e:
            self.logger.error(
                f"zarrwriter.py : writeSingleArray : Exception encountered - {e}"
            )
            raise AttemptingWriteWithoutFile()

    def threadedWriteSingleArray(self, *args, **kwargs):
        fs = []
        with lock_timeout(self.futures_lock):
            for f in self.futures:
                if f.done():
                    f.result()
                else:
                    fs.append(f)
            self.futures = fs

        f = self.executor.submit(self.writeSingleArray, *args)
        with lock_timeout(self.futures_lock):
            self.futures.append(f)

    def wait_all(self):
        wait(self.futures, return_when=ALL_COMPLETED)

    def closeFile(self):
        """Close the Zarr store."""
        self.writable = False
        wait(self.futures, return_when=ALL_COMPLETED)
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
