import inspect
from typing import Any


def is_async_context_manager(obj: Any) -> bool:
    return (
        hasattr(obj, "__aenter__")
        and inspect.iscoroutinefunction(obj.__aenter__)
        and hasattr(obj, "__aexit__")
        and inspect.iscoroutinefunction(obj.__aexit__)
    )
