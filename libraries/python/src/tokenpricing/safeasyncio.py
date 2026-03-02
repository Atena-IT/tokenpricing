import asyncio
import functools
import threading
from typing import Any, Callable, Coroutine, ParamSpec


P = ParamSpec("P")


class _AsyncThread(threading.Thread):
    """helper thread class for running async coroutines in a separate thread"""

    def __init__(self, coroutine: Coroutine[Any, Any, Any]):
        self.coroutine = coroutine
        self.result = None
        self.exception = None

        super().__init__(daemon=True)

    def run(self):
        try:
            self.result = asyncio.run(self.coroutine)
        except Exception as e:
            self.exception = e


def run_async_safely[T](
    coroutine: Coroutine[Any, Any, T], timeout: float | None = None
) -> T:
    """safely runs a coroutine with handling of an existing event loop.
    This function detects if there's already a running event loop and uses
    a separate thread if needed to avoid the "asyncio.run() cannot be called
    from a running event loop" error. This is particularly useful in environments
    like Jupyter notebooks, FastAPI applications, or other async frameworks.
    Args:
        coroutine: The coroutine to run
        timeout: max seconds to wait for. None means hanging forever
    Returns:
        The result of the coroutine
    Raises:
        Any exception raised by the coroutine
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # There's a running loop, use a separate thread
        thread = _AsyncThread(coroutine)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            raise TimeoutError("The operation timed out after %f seconds" % timeout)

        if thread.exception:
            raise thread.exception

        return thread.result
    else:
        if timeout:
            coroutine = asyncio.wait_for(coroutine, timeout)

        return asyncio.run(coroutine)


def make_sync(timeout: float | None = None):
    """decorator to convert an async function into a sync function.
    @make_sync, @make_sync(), or @make_sync(timeout=1.0)
    """

    def decorator[T](f: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, T]:
        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return run_async_safely(f(*args, **kwargs), timeout=timeout)

        return wrapper

    # use @make_sync without parentheses
    if callable(timeout):
        f = timeout
        timeout = None
        return decorator(f)

    return decorator
