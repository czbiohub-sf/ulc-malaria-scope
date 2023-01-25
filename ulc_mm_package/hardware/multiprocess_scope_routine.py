from __future__ import annotations

import abc
import ctypes
import numpy as np
import numpy.typing as npt
import multiprocessing as mp

from numbers import Real
from ctypes import _SimpleCData
from collections import namedtuple
from multiprocessing import sharedctypes
from typing import (
    cast,
    Dict,
    Type,
    Callable,
    Optional,
    Union,
    List,
    Tuple,
    NamedTuple,
)


"""
Ethos
-----

We want to be able to multiprocess some routines, in order to lighten the load
in the main process.

Further, we want this to be seamless with our current integration of scope routines.
That is, if you are writing code for QtGUI.scope_op, or writing a routine that takes
an image, does some computation, and returns a result.

- We want to pass images (eg np.array(dtype=u8, shape=(772,1032))) and values
  back/fourth across processes
- Using mp.Queue is slow due to the Pickle-ization + pipe through the kernel
- Use mp.Value, mp.Array (mem that is shared between processes!)
- copy time to mp.Array on RPi4 for u8 (772,1032) is:

    In [34]: random_img = np.random.randint(0,256,(772,1032))
    In [35]: %timeit np_arr[:] = random_img
    2.15 ms ± 538 ns per loop (mean ± std. dev. of 7 runs, 100 loops each)


What is "Shared Memory"?
------------------------

For Python's Multiprocessing, "Shared Memory" is fundamentally just a temporary file
to which Python will allocate and write. Since this file is a part of the file system,
it can be accessed (read/write) by other processes, provded they know the location of
the file. In practice, if you are on Linux, this file is allocated to `/dev/shm` [0][1]
which is in ram to keep it quick!

The interface for shared memory in Python multiprocessing is through mp.Value and
mp.Array. There are also mp.Value and mp.Array, but which are just their raw equivalents
with an associated lock. Values and Arrays are just ctypes under the hood which have
been allocated from shared memory (/dev/shm, /tmp, or /var/tmp)[2].

These ctypes can be a little finicky to work with. The original implementation of this had
a lot of 'if' statements on the type of the Value / Array. The final implementation
will wrap these ctypes in a manner that will

- have a unified API between Array / Value
- signify that it is a shared type as opposed to just a ctype

[0] https://github.com/python/cpython/blob/daec3a463c747c852d7ee91e82770fb1763d7d31/Lib/multiprocessing/heap.py#L73
[1] https://man7.org/linux/man-pages/man7/shm_overview.7.html
[2] https://github.com/python/cpython/blob/f02fa64bf2d03ef7a28650c164e17a5fb5d8543d/Lib/multiprocessing/sharedctypes.py#L44-L68


TODOs
-----

- I could make the shared memory type wrapper better. We define the arg types
  with 'ctypeDefn', which gets mapped to shared mem with `_defn_to_ctype`. Then every
  time we need to modify or read that memory, we have to do an if/else on the
  variable type! Messy messy messy.
    - abstracted into 'shared mem' class that has same interface for both shared
      memory types, just for cleanliness
- Rename "multiprocess_scope_routine.py" to a name that better reflects the true nature
  of the use of this file
- I am typing this *just* as values / arrays of Real numbers (i.e. work function arguments
  and return values are assumed to be real numbers). However, we can also support chars
  and limited strings (of fixed max length).
- Docs!
"""


class ctypeValueDefn(NamedTuple):
    type_str: str
    init_value: Real = cast(Real, 0)


class ctypeArrayDefn(NamedTuple):
    type_str: str
    shape: Tuple[int, int]


ctypeDefn = Union[ctypeValueDefn, ctypeArrayDefn]


_typecode_to_type: Dict[str, Type[_SimpleCData]] = {
    "c": ctypes.c_char,
    "u": ctypes.c_wchar,
    "b": ctypes.c_byte,
    "B": ctypes.c_ubyte,
    "h": ctypes.c_short,
    "H": ctypes.c_ushort,
    "i": ctypes.c_int,
    "I": ctypes.c_uint,
    "l": ctypes.c_long,
    "L": ctypes.c_ulong,
    "q": ctypes.c_longlong,
    "Q": ctypes.c_ulonglong,
    "f": ctypes.c_float,
    "d": ctypes.c_double,
}
_type_to_typecode = {v: k for k, v in _typecode_to_type.items()}

_ctype_codes = list(_typecode_to_type.keys())

_pytype = Union[Real, npt.NDArray[np.uint8]]
_ctype_type = Union[Type[_SimpleCData], str]


def get_ctype_image_defn(shape: Tuple[int, int]):
    "helper for common ctype"
    return ctypeArrayDefn("B", shape)


def get_ctype_float_defn():
    "helper for common ctype"
    return ctypeValueDefn("d")


class SharedctypeWrapper(abc.ABC):
    """
    Wraps shared memory (RawValue / RawArray) in a way
    that is easy to work with for the programmer.

    Typing for this class and it's subclasses make a lot
    more sense after reading this:

        https://github.com/python/typeshed/issues/8799

    """

    @classmethod
    def sharedctype_from_defn(cls, defn: ctypeDefn) -> SharedctypeWrapper:
        if isinstance(defn, ctypeValueDefn):
            return SharedctypeValue.from_definition(defn)
        elif isinstance(defn, ctypeArrayDefn):
            return SharedctypeArray.from_definition(defn)
        raise ValueError(f"invalid ctype defin: {defn}")

    def _ctype_defn_to_str(self, type_: _ctype_type) -> str:
        """mypy was complaining a lot, so we have to switch on type(type_) instead
        of doing the more elegant `return _type_to_typecode.get(type_, type_)` which
        has the same type garuntees"""
        if isinstance(type_, str):
            if not type_ in _ctype_codes:
                raise ValueError(f"invalid ctype code {type_}")
            return type_
        return _type_to_typecode[type_]

    @classmethod
    @abc.abstractmethod
    def from_definition(cls, defn: ctypeDefn) -> SharedctypeWrapper:
        """create SharedctypeWrapper from the given definition"""
        ...

    @abc.abstractmethod
    def set(self, v: _pytype) -> None:
        """Set the shared memory to the value of v"""
        ...

    def get(self) -> _pytype:
        """Get the shared memory and return as python
        type (e.g. numeric or numpy.ndarray)
        """
        ...


class SharedctypeValue(SharedctypeWrapper):
    def __init__(self, type_: _ctype_type, init_value: Optional[Real]):
        self._memory: mp.sharedctypes.Synchronized[Real] = mp.Value(type_, init_value)

    @classmethod
    def from_definition(cls, defn: ctypeDefn) -> SharedctypeValue:
        if not isinstance(defn, ctypeValueDefn):
            raise TypeError(
                f"need ctypeValueDefn to construct SharedctypeValue - got type {type(defn)}"
            )
        return cls(defn.type_str, defn.init_value)

    def set(self, v: _pytype) -> None:
        if not isinstance(v, Real):
            raise ValueError(f"set value for {self} is of incorrect type {type(v)}")

        with self._memory:
            self._memory.value = v

    def get(self) -> _pytype:
        with self._memory:
            return self._memory.value


class SharedctypeArray(SharedctypeWrapper):
    def __init__(self, type_: _ctype_type, shape: Tuple[int, ...]):
        self._lock = mp.Lock()

        size = int(np.prod(shape))

        type_ = self._ctype_defn_to_str(type_)
        self._memory = mp.RawArray(type_, size)
        self._np_wrapper = np.frombuffer(self._memory, dtype=type_).reshape(shape)

    @classmethod
    def from_definition(cls, defn: ctypeDefn) -> SharedctypeArray:
        if not isinstance(defn, ctypeArrayDefn):
            raise TypeError(
                f"need ctypeArrayDefn to construct SharedctypeArray - got type {type(defn)}"
            )
        return cls(defn.type_str, defn.shape)

    def set(self, v: _pytype) -> None:
        if not isinstance(v, np.ndarray):
            raise ValueError(f"set value for {self} is of incorrect type {type(v)}")

        with self._lock:
            self._np_wrapper[:] = v

    def get(self) -> _pytype:
        return self._np_wrapper


class MultiProcFunc:
    """multiprocess the execution of a function which takes an image and a timestamp"""

    def __init__(
        self,
        work_fcn: Callable,
        work_fn_inputs: List[SharedctypeWrapper],
        work_fn_outputs: List[SharedctypeWrapper],
    ):
        self.work_fcn: Callable = work_fcn

        self._input_ctypes = work_fn_inputs
        self._output_ctypes = work_fn_outputs

        # Flag used to know when we can either operate on the data or retrieve the result
        self._new_data_ready = mp.Event()
        self._ret_value_ready = mp.Event()

        self._proc = mp.Process(
            target=self._work,
            args=(self._input_ctypes, self._output_ctypes),
            daemon=True,
        )
        self._proc.start()

    @classmethod
    def from_arg_definitions(
        cls,
        work_fcn: Callable,
        work_fn_inputs: List[ctypeDefn],
        work_fn_outputs: List[ctypeDefn],
    ) -> MultiProcFunc:
        # Create the raw shared types for input/output of the function
        input_vals: List[SharedctypeWrapper] = [
            SharedctypeWrapper.sharedctype_from_defn(inp) for inp in work_fn_inputs
        ]
        output_vals: List[SharedctypeWrapper] = [
            SharedctypeWrapper.sharedctype_from_defn(out) for out in work_fn_outputs
        ]

        return cls(work_fcn, input_vals, output_vals)

    @staticmethod
    def _set_ctypes(
        set_values: List[_pytype], targets: List[SharedctypeWrapper]
    ) -> None:
        if len(set_values) != len(targets):
            raise ValueError("len(set_values) != len(targets)")

        for set_val, target in zip(set_values, targets):
            target.set(set_val)

    def _work(
        self, input_args: List[SharedctypeWrapper], outputs: List[SharedctypeWrapper]
    ) -> None:
        while True:
            self._new_data_ready.wait()
            self._new_data_ready.clear()

            func_args = [inp.get() for inp in self._input_ctypes]
            ret_vals = self.work_fcn(*func_args)
            ret_vals = ret_vals if isinstance(ret_vals, tuple) else [ret_vals]

            self._set_ctypes(ret_vals, outputs)

            self._ret_value_ready.set()

    def call(self, args: List[_pytype]) -> Tuple[_pytype, ...]:
        self._set_ctypes(args, self._input_ctypes)

        return self._func_call()

    def _func_call(self) -> Tuple[_pytype, ...]:
        """
        if self._input_ctypes has been set somewhere else,
        we want to still be able to smoothly call the work func
        """
        self._new_data_ready.set()

        self._ret_value_ready.wait()
        self._ret_value_ready.clear()

        return tuple(out.get() for out in self._output_ctypes)

    def join(self) -> None:
        self._proc.join()
