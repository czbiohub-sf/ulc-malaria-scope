import functools

from typing import Optional
from contextlib import contextmanager


def lockNoBlock(lock, exception):

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
def lock_timeout(lock, timeout: Optional[float] = None):
    """lock context manager w/ timeout

    timeout value of 'None' or negative numbers disables timeout
    """
    if timeout is None or timeout < 0:
        timeout = -1

    lock.acquire(timeout=timeout)
    try:
        yield
    finally:
        lock.release()
