import warnings
from functools import wraps
from typing import Any, Callable


def deprecated_api(since: str, remove_in: str) -> Callable:
    """
    Decorator that marks a function or method as deprecated.

    Emits a DeprecationWarning when the decorated function is called.

    Args:
        since: Version string indicating when the API was deprecated.
        remove_in: Version string indicating when the API will be removed.

    Returns:
        The wrapped function (unchanged behavior, but warns on call).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(
                f"{func.__name__} is deprecated since {since} and "
                f"will be removed in {remove_in}.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator
