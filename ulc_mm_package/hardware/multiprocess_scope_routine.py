"""
We want to be able to multiprocess some routines, in order to lighten the load
in the main process.

Further, we want this to be seamless with our current integration of scope routines.
That is, if you are writing code for QtGUI.scope_op, or writing a routine that takes
an image, does some computation, and returns a result.
"""

import ctypes
import numpy as np
import numpy.typing as npt
import multiprocessing as mp

from collections import namedtuple
from typing import TypeVar, Callable, Optional, Union, List, Tuple


"""
- We want to pass images np.array(dtype=u8, shape=(772,1032)) and values back/fourth across processes
- Using mp.Queue is slow due to the Pickleization + pipe through the kernel
- Use mp.Value, mp.Array
- copy time is u8 (772,1032):

    In [35]: %timeit np_arr[:] = random_img
    2.15 ms ± 538 ns per loop (mean ± std. dev. of 7 runs, 100 loops each)

- I don't really like how we are doing the handling of moving data here;
  it needs to be refactored for clarity.
"""


ctypeValueDefn = namedtuple("ctypeValueDefn", ["type_str", "init_value"])
ctypeArrayDefn = namedtuple("ctypeArrayDefn", ["type_str", "shape"])

ctypeDefn = Union[ctypeValueDefn, ctypeArrayDefn]

AVTImg = npt.NDArray[np.uint8]
ctype = Union[ctypes.c_float, AVTImg]


def type_to_ctype_equiv(val: Union[npt.NDArray, float], ctype_val: ctype):
    if isinstance(val, float) and isinstance(ctype_val, ctypes.c_float):
        # TODO generalize for ctypes other than c_float
        return True
    elif isinstance(val, np.ndarray) and isinstance(ctype_val, np.ndarray):
        have_equiv_types = val.dtype == ctype_val.dtype
        have_same_shape = val.shape == ctype_val.shape
        return have_equiv_types and have_same_shape
    return False


def get_ctype_image_defn(shape: Tuple[int, int]) -> ctypeArrayDefn:
    "helper function for our images"
    return ctypeArrayDefn(type_str="B", shape=shape)


def get_ctype_float_defn(init_value: float = 0.0) -> ctypeValueDefn:
    "helper function for a float"
    return ctypeValueDefn(type_str="f", init_value=init_value)


class MultiProcFunc:
    """multiprocess the execution of a function which takes an image and a timestamp"""

    def __init__(
        self,
        work_fcn: Callable,
        work_fn_inputs: List[ctypeDefn],
        work_fn_outputs: List[ctypeDefn],
    ):
        self.work_fcn: Callable = work_fcn

        # Create the raw shared types for input/output of the function
        self._input_ctypes: List[ctype] = [
            self._defn_to_ctype(d) for d in work_fn_inputs
        ]
        self._output_ctypes: List[ctype] = [
            self._defn_to_ctype(d) for d in work_fn_outputs
        ]

        # raw array / value because the input Array and Value are changed together
        # this may not even be necessary depending on our impl
        self._value_lock = mp.Lock()

        # Flag used to know when we can either operate on the data or retrieve the result
        self._new_data_ready = mp.Event()
        self._ret_value_ready = mp.Event()

        self._proc = mp.Process(
            target=self._work,
            args=(self._input_ctypes, self._output_ctypes),
            daemon=True,
        )
        self._proc.start()

    @staticmethod
    def _defn_to_ctype(ctype_defn: ctypeDefn) -> ctype:
        """
        Convert our type defns to actual shared memory. To be used only in MultiProcFunc
        """
        if isinstance(ctype_defn, ctypeValueDefn):
            return mp.RawValue(ctype_defn.type_str, ctype_defn.init_value)
        elif isinstance(ctype_defn, ctypeArrayDefn):
            # i think that RawArray isn't being updated in the child process! fuck!
            return np.frombuffer(
                mp.RawArray(ctype_defn.type_str, int(np.prod(ctype_defn.shape))),
                dtype=ctype_defn.type_str,
            ).reshape(ctype_defn.shape)

        raise ValueError(f"needed a ctypeDefn: got {type(ctype_defn)}")

    @staticmethod
    def _set_ctypes(set_values: List[Union[npt.NDArray, float]], targets: List[ctype]):
        if len(set_values) != len(targets):
            raise ValueError("len(set_values) != len(targets)")

        for set_val, target in zip(set_values, targets):
            if not type_to_ctype_equiv(set_val, target):
                raise ValueError(
                    f"set value and target ctype value are not "
                    f"equivalent: set_val = {set_val}, target_val = {target}"
                )
            if isinstance(set_val, np.ndarray):
                # for mypy
                assert isinstance(target, np.ndarray)
                target[:] = set_val
            else:
                # for mypy
                assert isinstance(target, ctypes.c_float)
                target.value = set_val

    @staticmethod
    def _get_data_from_ctypes(
        targets: List[ctype], copy: bool = True
    ) -> List[Union[npt.NDArray, float]]:
        def get_python_value(ctype_val: ctype) -> Union[npt.NDArray, float]:
            if isinstance(ctype_val, np.ndarray):
                if copy:
                    return np.copy(ctype_val)
                return ctype_val
            else:
                return ctype_val.value

        return [get_python_value(c) for c in targets]

    def _work(self, input_args, outputs):
        while True:
            self._new_data_ready.wait()
            self._new_data_ready.clear()

            with self._value_lock:
                func_args = self._get_data_from_ctypes(input_args, copy=False)
                ret_vals = self.work_fcn(*func_args)

                self._set_ctypes([ret_vals], outputs)

            self._ret_value_ready.set()

    def call(
        self, args: List[Union[npt.NDArray, float]]
    ) -> Tuple[Union[npt.NDArray, float], ...]:
        with self._value_lock:
            self._set_ctypes(args, self._input_ctypes)
        self._new_data_ready.set()

        self._ret_value_ready.wait()
        self._ret_value_ready.clear()

        with self._value_lock:
            return tuple(self._get_data_from_ctypes(self._output_ctypes))

    def join(self):
        self._proc.join()
