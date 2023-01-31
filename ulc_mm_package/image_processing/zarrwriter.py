""" Simple Zarr storage format wrapper

-- Important Links --
Library Documentation:
    https://zarr.readthedocs.io/en/stable/index.html

"""

import time
import zarr
import logging
import threading
import functools
import threading
import numpy as np

from time import perf_counter
from typing import cast, List, Tuple, Optional
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, Future, wait

import ulc_mm_package.hardware.multiprocess_scope_routine as msr

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

        self.writing_process = msr.MultiProcFunc.from_arg_definitions(
            self._write_single_array,
            [msr.get_ctype_image_defn((772, 1032)), msr.get_ctype_int_defn()],
            [],
        )

    def create_new_file(self, filename: str, overwrite: bool = True):
        """Create a new zarr file.

        Parameters
        ----------
        filename : str
            Filename, don't include the extension (i.e pass "new_file" not "new_file.zip").
        overwrite : bool
            Will overwrite a file with the existing filename if it exists, otherwise will append.
        """
        print("creating new file")
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
            print(f'now wriitable')
        except AttributeError as e:
            self.logger.error(
                f"zarrwriter.py : createNewFile : Exception encountered - {e}"
            )
            raise IOError(f"Error creating {filename}.zip")

    def threaded_write_single_array(self, data, pos: int):
        for g in self.futures: g.result()
        print('threaded_write_single_array')
        f = self.executor.submit(self.write_single_array, data, pos)
        self.futures.append(f)
        print('threaded_write_single_array end')

    def write_single_array(self, data: np.ndarray, pos: int) -> None:
        # need to be explicit about types here!
        l: List[msr._pytype] = [data, cast(msr._pytype, pos)]
        print('write_single_array')
        self.writing_process.call(l)
        print('write_single_array end')

    def _write_single_array(self, data, pos: int) -> None:
        """Write a single array and optional metadata to the Zarr store.

        Parameters
        ----------
        data : np.ndarray - the image to write
        pos: int - the index of the zarr array to write to

        Since each `pos` is a different chunk, it is threadsafe - see
        https://zarr.readthedocs.io/en/stable/tutorial.html#parallel-computing-and-synchronization
        """
        print(f"in _write_single_array {pos} writable = {self.writable}")
        if not self.writable:
            print('not writable so _write_single_array is leaving')
            return

        print(f'writing to arr {pos}')

        try:
            self.array[:, :, pos] = data
        except Exception as e:
            self.logger.error(
                f"zarrwriter.py : writeSingleArray : Exception encountered - {e}"
            )
            # FIXME is this the only exception? we should make it a general "ZarrWriterMessedUp" error
            raise AttemptingWriteWithoutFile()

        print(f'done {pos}')

    def wait_all(self):
        wait(self.futures, return_when=ALL_COMPLETED)

    def close_file(self):
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

    def threaded_close_file(self):
        """Close the file in a separate thread.

        This threaded close was written with UI.py in mind, so that the file can be closed while
        keeping the rest of the GUI responsive.

        Returns
        -------
        future: An object that can be polled to check if closing the file has completed
        """
        return self.executor.submit(self.close_file)
