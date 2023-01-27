from __future__ import annotations

import abc
import queue
import ctypes
import numpy as np
import numpy.typing as npt
import multiprocessing as mp

from numbers import Real
from ctypes import _SimpleCData
from collections import namedtuple
from contextlib import contextmanager
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
  back/forth across processes
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
it can be accessed (read/write) by other processes, provided they know the location of
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


Future additions
----------------

- I am typing this *just* as values / arrays of Real numbers (i.e. work function arguments
  and return values are assumed to be real numbers). However, we can also support chars
  and limited strings (of fixed max length).
"""


@contextmanager
def lock_timeout(lock, timeout: Optional[float] = None):
    """lock context manager w/ timeout

    timeout value of 'None' or negative numbers disables timeout
    """
    if timeout is None or timeout < 0:
        timeout = -1

    acquired = lock.acquire(timeout=timeout)
    if not acquired:
        raise SharedctypeLockTimeout("could not acquire lock to set value")

    try:
        yield
    finally:
        lock.release()


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


class SharedctypeLockTimeout(Exception):
    ...


class SharedctypeWrapper(abc.ABC):
    """
    Wraps shared memory (RawValue / RawArray / Value / Array)
    in a way that is easy to work with for the programmer.

    Typing for this class and its subclasses make a lot
    more sense after reading this:

        https://github.com/python/typeshed/issues/8799

    A `SharedctypeWrapper` must implement `set` and `get`, which
    set the shared memory to some value, and returns a python object
    that represents the shared memory, respectively.
    """

    @classmethod
    def sharedctype_from_defn(cls, defn: ctypeDefn) -> SharedctypeWrapper:
        """
        This function can be used to turn a cytpeDefn to a
        shared ctype (either a SharedctypeValue or SharedCtypeArray)
        """
        if isinstance(defn, ctypeValueDefn):
            return SharedctypeValue.from_definition(defn)
        elif isinstance(defn, ctypeArrayDefn):
            return SharedctypeArray.from_definition(defn)
        raise ValueError(f"invalid ctype defin: {defn}")

    def _ctype_defn_to_str(self, type_: _ctype_type) -> str:
        """mypy was complaining a lot, so we have to switch on type(type_) instead
        of doing the more elegant `return _type_to_typecode.get(type_, type_)` which
        has the same type guarantee"""
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

    def set(self, v: _pytype, timeout: Optional[float] = 1.0) -> None:
        """
        Try to set the shared memory to v

        If we can't acquire the lock in `timeout` seconds, raise SharedctypeLockTimeout.
        `timeout=None` means block indefinitely
        """
        if not isinstance(v, Real):
            raise ValueError(f"set value for {self} is of incorrect type {type(v)}")

        with lock_timeout(self._memory.get_lock(), timeout=timeout):
            self._memory.value = v

    def get(self, timeout: Optional[float] = 1.0) -> _pytype:
        """
        Try to get the shared memory value

        If we can't acquire the lock in `timeout` seconds, raise SharedctypeLockTimeout.
        `timeout=None` means block indefinitely
        """
        with lock_timeout(self._memory.get_lock(), timeout=timeout):
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

    def set(self, v: _pytype, timeout: Optional[float] = 1.0) -> None:
        """
        Try to set the shared memory to v.

        If we can't acquire the lock in `timeout` seconds, raise SharedctypeLockTimeout.
        `timeout=None` means block indefinitely
        """
        if not isinstance(v, np.ndarray):
            raise ValueError(f"set value for {self} is of incorrect type {type(v)}")

        with lock_timeout(self._lock, timeout=timeout):
            self._np_wrapper[:] = v

    def get(self) -> _pytype:
        """
        return a copy of the numpy array
        """
        return self._np_wrapper.copy()


class MultiProcFuncHalted(Exception):
    ...


class MultiProcFuncTerminated(Exception):
    ...


class MultiProcFunc:
    """Multiprocess a given function with a framework to rapidly pass arguments
    and return values between the processes.

    As discussed at the top of the file, it can take quite a while for a mp.Queue
    to pass a value between processes, due to the pickle-pipe-unpickle steps. This
    uses shared memory between the processes to pass values back and forth.

    Example Usage:

    >>> def heavy_func(img, val):
    ...     "some arbitrary heavy calc (e.g. a bunch of math)"
    ...     s = 0
    ...     for i in range(1, 5 + 1):
    ...         s += (val / i) * ((img.T @ img) @ img.T).sum()
    ...     return s

    >>> # the input img
    >>> img = np.random.randint(0, 256, (772, 1032), dtype=np.uint8)

    >>> # now define the shape and datatypes for the image
    >>> img_defn = get_ctype_image_defn((772, 1032))
    >>> # define an input value
    >>> value_defn_input = get_ctype_float_defn()
    >>> # define an output value
    >>> value_defn_output = get_ctype_float_defn()

    >>> # Create the `MultiProcFunc` from the arg definitions
    >>> # if you have already created shared memory using
    >>> # 'SharedctypeWrapper.sharedctype_from_defn`, then you
    >>> # can directly initialize the `MultiProcFunc`! This would
    >>> # be useful if you update variables over time (e.g. see
    >>> # image_processing/flowrate.py
    >>> m = MultiProcFunc.from_arg_definitions(
    ...     heavy_func, [img_defn, value_defn_input], [value_defn_output]
    ... )

    >>> # Put it to work!
    >>> for i in range(10):
    ...     # this call to work will be in the second process
    ...     print("result: ", m.call([img, float(i)]))
    """

    NEW_DATA_TIMEOUT = 1

    def __init__(
        self,
        work_fcn: Callable,
        work_fn_inputs: List[SharedctypeWrapper],
        work_fn_outputs: List[SharedctypeWrapper],
    ):
        self.work_fcn: Callable = work_fcn

        self._input_ctypes = work_fn_inputs
        self._output_ctypes = work_fn_outputs

        # Flags used to know when we can either operate
        # on the data or retrieve the result
        self._new_data_ready = mp.Event()
        self._ret_value_ready = mp.Event()

        # halt and join the process if set
        # to get the process to run, _halt_flag must be clear.
        self._halt_flag = mp.Event()

        self._exception_queue: mp.Queue[Exception] = mp.Queue(maxsize=1)

        self.start()

    def start(self) -> None:
        self._halt_flag.clear()

        self._proc = mp.Process(
            target=self._work,
            args=(self._input_ctypes, self._output_ctypes),
            daemon=True,
        )
        self._proc.start()

    def stop(self, timeout: float = 3.0) -> None:
        """
        Stop and join the main process. Timeout for
        `max(timeout, NEW_DATA_TIMEOUT)` so we can
        let the internal process join gracefully.

        After timing out, the process will be terminated,
        and this object will not be able to be used again
        unless restarted or reinitialized.

        From python Multiprocessing docs 3.7:

            "Note that the method returns None if its
             process terminates or if the method times
             out. Check the process’s exitcode to
             determine if it terminated."

        The exit code doc:

            "This will be None if the process has not
            yet terminated. A negative value -N indicates
            that the child was terminated by signal N."

        Terminating a process is not without risk:

            "Warning: If this method is used when the
            associated process is using a pipe or queue
            then the pipe or queue is liable to become
            corrupted and may become unusable by other
            process. Similarly, if the process has acquired
            a lock or semaphore etc. then terminating it
            is liable to cause other processes to deadlock."

        Since this class should be the only class that is accessing
        the process, we shouldn't have to worry about deadlocks.
        However, we should probably re-instantiate the shared mem.
        """
        self._halt_flag.set()
        self._proc.join(timeout=timeout)

        if self._proc.exitcode is None:
            # the 'join' timed out, we must terminate the process
            self._proc.terminate()
            raise MultiProcFuncTerminated(
                "internal process had to be terminated; re-initialize the "
                "MultiProcFunc to continue using it"
            )

    @classmethod
    def from_arg_definitions(
        cls,
        work_fcn: Callable,
        work_fn_inputs: List[ctypeDefn],
        work_fn_outputs: List[ctypeDefn],
    ) -> MultiProcFunc:
        """
        Create a MultiProcFunc from the work_fcn and input definitions
        """
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
        """
        Set the ctypes from the pythonic types
        """
        if len(set_values) != len(targets):
            raise ValueError("len(set_values) != len(targets)")

        for set_val, target in zip(set_values, targets):
            target.set(set_val)

    def _work(
        self, input_args: List[SharedctypeWrapper], outputs: List[SharedctypeWrapper]
    ) -> None:
        """
        This is where the actual work happens (in another process, of course).

        Here, we
        1. wait for new data to be ready (i.e. new values are in the input ctypes)
        2. clear the new data flag so it can be set again
        3. get python values from the input ctypes
        4. do the actual calculation (i.e. call self.work_fcn)
        5. set the output cytpes to the return value from work function
        6. flag the main process that there is a return  value to be read
        """
        while not self._halt_flag.is_set():
            # the check for new data - timeout to check if we are being halted
            try:
                new_data_ready = self._new_data_ready.wait(
                    timeout=self.NEW_DATA_TIMEOUT
                )

                if new_data_ready:
                    self._new_data_ready.clear()

                    func_args = [inp.get() for inp in self._input_ctypes]
                    ret_vals = self.work_fcn(*func_args)
                    ret_vals = ret_vals if isinstance(ret_vals, tuple) else [ret_vals]

                    self._set_ctypes(ret_vals, outputs)

                    self._ret_value_ready.set()
            except Exception as e:
                self._halt_flag.set()
                try:
                    self._exception_queue.put_nowait(e)
                except queue.Full:
                    # put the most recent exception in
                    self._exception_queue.get_nowait()
                    self._exception_queue.put_nowait(e)
                    self._exception_queue.task_done()

    def call(self, args: List[_pytype]) -> Union[_pytype, Tuple[_pytype, ...]]:
        """
        Call the _work function given args.

        We've separated this function from _func_call so, if needed,
        we can set input variables in advance and do the function call
        sometime in the future when needed.
        """
        self._set_ctypes(args, self._input_ctypes)

        return self._func_call()

    def _func_call(self) -> Union[_pytype, Tuple[_pytype, ...]]:
        """
        If self._input_ctypes has been set somewhere else,
        we want to still be able to smoothly call the work func.

        Here, we assume that self._input_ctypes has already been set.
        Then, we
        1. flag that there is new data ready
        2. wait for the return value to be ready
        3. return the python values from the ctype
        """
        try:
            exc = self._exception_queue.get_nowait()
            self._exception_queue.task_done()
            raise exc
        except queue.Empty:
            # if the queue is empty, then there are no exceptions :)
            pass

        if self._halt_flag.is_set():
            # we are trying to call on a halted MultiProcFunc instance!
            raise MultiProcFuncHalted(
                "MultiProcFunc has been halted! restart or reinitialize it"
            )

        self._new_data_ready.set()

        self._ret_value_ready.wait()
        self._ret_value_ready.clear()

        out_vals = tuple(out.get() for out in self._output_ctypes)

        if len(out_vals) == 1:
            return out_vals[0]
        return out_vals
