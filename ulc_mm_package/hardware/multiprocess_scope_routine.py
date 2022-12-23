"""
We want to be able to multiprocess some routines, in order to lighten the load
in the main process.

Further, we want this to be seamless with our current integration of scope routines.
That is, if you are writing code for QtGUI.scope_op, or writing a routine that takes
an image, does some computation, and returns a result.

The way we do this is this:
    - initialize and put your routine in a
"""

import multiprocessing as mp

from typing import TypeVar, Callable, Optional

T = TypeVar("T")
G = TypeVar("G")


class MultiProcessScopeRoutine:
    def __init__(self, work_fcn):
        self.work_fcn: Callable[..., G] = work_fcn
        self._args_queue: mp.Queue[T] = mp.Queue()
        self._ret_queue: mp.Queue[G] = mp.Queue()
        self._proc = mp.Process(target=self._work)

    def _work(self):
        in_obj = self._args_queue.get()
        ret_val = self.work_fcn(*in_obj)
        self._ret_queue.put(ret_val)

    def put(self, el: T, block: bool = True, timeout: Optional[float] = None):
        self._args_queue.put(el, block=block, timeout=timeout)

    def get(self, block: bool = True, timeout: Optional[float] = None) -> G:
        self._ret_queue.get(block=block, timeout=timeout)

    def start(self):
        self._proc.start()

    def join(self):
        self._proc.join()
