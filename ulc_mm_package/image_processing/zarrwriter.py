""" Simple Zarr storage format wrapper

-- Important Links --
Library Documentation:
    https://zarr.readthedocs.io/en/stable/index.html

"""

import zarr
import logging

from typing import List
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, Future, wait

from ulc_mm_package.scope_constants import CameraOptions, CAMERA_SELECTION, MAX_FRAMES


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


class ZarrWriter:
    def __init__(self, camera_selection: CameraOptions = CAMERA_SELECTION):
        self.writable = False
        self.futures: List[Future] = []
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=1)

        self.camera_selection: CameraOptions = camera_selection

    def createNewFile(self, filename: str, overwrite: bool = True):
        """Create a new zarr file.

        Parameters
        ----------
        filename : str
            Filename, don't include the extension (i.e pass "new_file" not "new_file.zip").
        overwrite : bool
            Will overwrite a file with the existing filename if it exists, otherwise will append.
        """
        try:
            self.store = zarr.ZipStore(
                f"{filename}.zip",
                mode="w" if overwrite else "x",
            )
            self.array = zarr.zeros(
                shape=(
                    self.camera_selection.IMG_HEIGHT,
                    self.camera_selection.IMG_WIDTH,
                    MAX_FRAMES,
                ),
                chunks=(
                    self.camera_selection.IMG_HEIGHT,
                    self.camera_selection.IMG_WIDTH,
                    1,
                ),
                compressor=None,
                store=self.store,
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
        if not self.writable:
            return

        try:
            self.array[:, :, pos] = data
        except Exception as e:
            self.logger.error(
                f"zarrwriter.py : writeSingleArray : Exception encountered - {e}"
            )
            raise AttemptingWriteWithoutFile()

    def threadedWriteSingleArray(self, data, pos: int):
        f = self.executor.submit(self.writeSingleArray, data, pos)
        self.futures.append(f)

    def wait_all(self):
        wait(self.futures, return_when=ALL_COMPLETED)

    def closeFile(self):
        """Close the Zarr store."""
        self.writable = False
        self.wait_all()

        exceptions = []
        for f in self.futures:
            if f.exception() is not None:
                exceptions.append(f.exception())

        for i, exc in enumerate(exceptions):
            self.logger.error(f"exception in zarrwriter: {exc}")
            if i > 10:
                self.logger.error(
                    f"{len(exceptions) - i} exceptions left; {len(exceptions)} total"
                )
                break

        self.futures = []
        self.store.close()

    def threadedCloseFile(self):
        """Close the file in a separate thread.

        This threaded close was written with UI.py in mind, so that the file can be closed while
        keeping the rest of the GUI responsive.

        Returns
        -------
        future: An object that can be polled to check if closing the file has completed
        """
        return self.executor.submit(self.closeFile)
