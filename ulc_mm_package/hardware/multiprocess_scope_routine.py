"""
We want to be able to multiprocess some routines, in order to lighten the load
in the main process.

Further, we want this to be seamless with our current integration of scope routines.
That is, if you are writing code for QtGUI.scope_op, or writing a routine that takes
an image, does some computation, and returns a result.
"""

import multiprocessing as mp

from collections import namedtuple
from typing import TypeVar, Callable, Optional, Union

T = TypeVar("T")
G = TypeVar("G")


"""
- We want to pass images np.array(dtype=u8, shape=(772,1032)) and values back/fourth across processes
- Using mp.Queue is slow due to the Pickleization + pipe through the kernel
- Use mp.Value, mp.Array
- copy time is:

    In [35]: %timeit np_arr[:] = random_img
    2.15 ms ± 538 ns per loop (mean ± std. dev. of 7 runs, 100 loops each)

"""


ctypeValueDefn = namedtuple("ctypeValueDefn", ["type_str", "init_value"])
ctypeArrayDefn = namedtuple("ctypeArrayDefn", ["type_str", "shape"])

def get_ctypeImage_defn(shape: Tuple[int,int]):
    "helper function for common ctype defn"
    return ctypeArrayDefn(type_str="b", shape=shape)


ctypeDefn = Union[ctypeValueDefn, ctypeArrayDefn]
ctype = Union[mp.Value, mp.Array]


class MultiProcessScopeRoutine:
    """
    can take numpy arrays (of dtype following these type codes https://docs.python.org/3/library/array.html#module-array
    """
    def __init__(self, work_fn: Callable, work_fn_inputs: List[ctypeDefn], work_fn_outputs: List[ctypeDefn]):
        self.input_ctype_defns = work_fn_inputs
        self.output_ctype_defns = work_fn_outputs

        self.input_ctypes = self._gen_ctypes(work_fn_inputs)
        self.output_ctypes = self._gen_ctypes(work_fn_outputs)

    def _gen_ctypes(self, ctype_defns: List[ctypeDefn]) -> List[ctype]:

        def defn_to_ctype(ctype_defn: ctypeDefn) -> ctype:
            if isinstance(ctype_defn, ctypeValueDefn):
                return mp.Value(ctype_defn.type_str, ctype_defn.init_value)
            elif isinstance(ctype_defn, ctypeArrayDefn):
                return mp.Array(ctype_defn.type_str, np.prod(ctype.shape))
            raise ValueError(f"needed ctypeDefn: got {type(ctype_defn)}")

        return [defn_to_ctype(d) for d in ctype_defns]

    def put(self, args):
        if len(args) != len(self.input_ctype):
            raise ValueError(f"length of args ({len(args)}) != length of work fn. input ({len(self.input_ctypes)})")

        for ctype, ctype_defn, arg in zip(self.input_ctypes, self.input_ctype_defns, args):
            if isinstance(ctype, mp.Value):
                with ctype.get_lock():
                    ctype.value = arg
            elif isinstance(ctype, mp.Array):
                with ctype.get_lock():
                    ctype.value


class MultiProcessScopeRoutineSlOW:
    def __init__(self, work_fcn):
        self.work_fcn: Callable[..., G] = work_fcn
        self._args_queue: mp.Queue[T] = mp.Queue()
        self._ret_queue: mp.Queue[G] = mp.Queue()
        self._proc = mp.Process(target=self._work, daemon=True)
        self.start()

    def _work(self):
        while True:
            in_obj = self._args_queue.get()
            ret_val = self.work_fcn(*in_obj)
            self._ret_queue.put(ret_val)

    def put(self, el: T, block: bool = True, timeout: Optional[float] = None):
        self._args_queue.put(el, block=block, timeout=timeout)

    def get(self, block: bool = True, timeout: Optional[float] = None) -> G:
        return self._ret_queue.get(block=block, timeout=timeout)

    def start(self):
        self._proc.start()

    def join(self):
        self._proc.join()
