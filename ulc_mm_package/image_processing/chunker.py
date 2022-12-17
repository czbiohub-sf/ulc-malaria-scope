import threading
import numpy as np

from typing import Tuple, List


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
