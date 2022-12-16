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
from typing import List, Tuple, Optional
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


class ChunkSelector:
    """
    TODO:
        idx ranges to write to zarr array
        idx verification (we want to write an entire chunk)
    """

    def __init__(self, shape: Tuple[int, int, int], num_chunks: int):
        if len(shape) != 3:
            raise ValueError(
                f"ChunkSelector initialized improperly; must be (h,w,num_chunks), got {shape}"
            )

        self.num_chunks = num_chunks
        self.h, self.w, self.chunk_size = shape

        # the chunks
        self._chunks: List[np.ndarray] = [
            np.zeros(shape, dtype=np.uint8) for _ in range(num_chunks)
        ]

        # flags indicating if the chunk is writable
        self._writable: List[threading.Event] = [
            threading.Event() for _ in range(num_chunks)
        ]

        # number of images written per chunk
        self._chunk_img_idx: List[int] = [0 for _ in range(num_chunks)]

        # _current_chunk_idx in Z mod num_chunks
        self._current_chunk_idx: int = 0

        # all chunks are writable initially!
        for w in self._writable:
            w.set()

    def current_chunk(self) -> np.ndarray:
        return self._chunks[self._current_chunk_idx]

    def current_chunk_img_idx(self) -> int:
        return self._chunk_img_idx[self._current_chunk_idx]

    def write_img(
        self, img: np.ndarray
    ) -> Optional[Tuple[np.ndarray, threading.Event]]:
        """
        - if chunk isn't ready, return None
        - if it is, return the chunk and a flag to denote when it is OK to write to again
        - the future that is doing the writing must set the flag once it is done with it
        """
        chunk = self.current_chunk()
        chunk_img_idx = self.current_chunk_img_idx()

        if self._writable[self._current_chunk_idx].is_set():
            # chunk is writable! set the image as the next chunk slice
            chunk[:, :, chunk_img_idx] = img
        else:
            # wait for next chunk because we do not want to lose this image
            # TODO: add to queue? Yuck!
            self.select_next_chunk(wait=True)
            return self.write_img(img)

        # increment the chunk idx
        self._chunk_img_idx[self._current_chunk_idx] += 1

        if self._chunk_img_idx[self._current_chunk_idx] == self.chunk_size:
            # written `chunk_size` images, so this chunk is ready to write
            written_chunk_event = self._writable[self._current_chunk_idx]
            written_chunk_event.clear()  # no longer writable
            self.select_next_chunk()
            return chunk, written_chunk_event

        return None

    def select_next_chunk(self, wait=False) -> bool:
        """
        select next chunk. If there is a chunk that is writable, return true.
        if `wait=False`, and there are no chunks that are writable, return
        false imediately.
        """
        if wait:
            self._current_chunk_idx = self.wait_on_next_writable()
            return True

        for i in range(self.num_chunks):
            next_chunk_idx = (self._current_chunk_idx + i) % self.num_chunks
            if self._writable[next_chunk_idx].is_set():
                self._current_chunk_idx = next_chunk_idx
                return True

        return False

    def wait_on_next_writable(
        self, timeout: float = 0.0005, total_timeout: float = 10.0
    ) -> int:
        """
        wait for the next writable chunk and return it's index.

        timeout - time to wait per event before checking the next one. The lower the timeout, the faster
        we will find the next available chunk, but the more CPU we will be using

        total_timeout - total time before we give up and raise an error
        """
        i = (self._current_chunk_idx + 1) % self.num_chunks
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < total_timeout:
            # wait will return True if the Event is set, else False
            if self._writable[i].wait(timeout=timeout):
                return i
            i = (i + 1) % self.num_chunks
        raise RuntimeError(f"no chunks writable after {total_timeout} seconds")


N = 16


class ZarrWriter:
    def __init__(self, camera_selection: CameraOptions = CAMERA_SELECTION):
        self.writable = False
        self.futures: List[Future] = []
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=16)

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
            filename = f"{filename}.zip"
            self.array = zarr.open(
                filename,
                "w" if overwrite else "x",
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
            if f.exception is not None:
                exceptions.append(f.exception)

        for i, exc in enumerate(exceptions):
            self.logger.error(f"exception in zarrwriter: {exc}")
            if i > 10:
                self.logger.error(
                    f"{len(exceptions) - i} exceptions left; {len(exceptions)} total"
                )
                break

        self.futures = []

    def threadedCloseFile(self):
        """Close the file in a separate thread.

        This threaded close was written with UI.py in mind, so that the file can be closed while
        keeping the rest of the GUI responsive.

        Returns
        -------
        future: An object that can be polled to check if closing the file has completed
        """
        return self.executor.submit(self.closeFile)
