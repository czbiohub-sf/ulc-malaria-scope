import functools

from threading import Lock
from typing import Optional
from contextlib import contextmanager


def lock_no_block(lock, exception):
    """
    decorator to try to lock the given `lock`, and if you can
    not lock immediately, then raise `exception`
    """

    def lockDecorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not lock.locked():
                with lock:
                    return func(*args, **kwargs)
            else:
                raise exception

        return wrapper

    return lockDecorator


@contextmanager
def lock_timeout(lock: Lock, timeout: Optional[float] = None):
    """lock context manager w/ timeout

    timeout value of 'None' or negative numbers disables timeout
    """
    if timeout is None or timeout < 0:
        timeout = -1

    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        if lock.locked():
            lock.release()
