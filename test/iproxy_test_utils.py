"""Simple utilities for running IProxy tests with pytest

This provides a minimal approach to make IProxy tests work with pytest
without requiring complex plugins or conversions.
"""

from typing import Any, Optional
from pinjected import IProxy, design
from pinjected.test.injected_pytest import _to_pytest


def to_pytest(iproxy: IProxy, module_design: Optional[Any] = None) -> Any:
    """Convert an IProxy test to a pytest function

    This is a simple wrapper around pinjected's _to_pytest that handles
    the common case of converting IProxy tests.

    Usage:
        # At the top of your test file
        from test.iproxy_test_utils import to_pytest

        # Define your IProxy test
        test_something_iproxy: IProxy = my_test_function(dependencies)

        # Convert to pytest
        test_something = to_pytest(test_something_iproxy)

    Args:
        iproxy: The IProxy test object to convert
        module_design: Optional design configuration (uses default if not provided)

    Returns:
        A pytest-compatible test function
    """
    import inspect

    # Get caller's frame to find the file path and design
    frame = inspect.currentframe().f_back
    file_path = frame.f_globals.get("__file__", "<unknown>")

    # Use provided design or try to get from caller's module
    if module_design is None:
        module_design = frame.f_globals.get("__meta_design__", design())

    return _to_pytest(iproxy, module_design, file_path)


# Simple example usage in docstring
__doc__ += """

Example usage in a test file:

```python
from pathlib import Path
from pinjected import IProxy, injected, design
from test.iproxy_test_utils import to_pytest
from ml_nexus.schematics_util.universal import schematics_universal
from loguru import logger

# Define your IProxy test
@injected
async def a_test_example(schematics_universal, logger):
    '''Test example'''
    result = await schematics_universal(...)
    assert result is not None
    return True

# Create IProxy object
test_example_iproxy: IProxy = a_test_example(schematics_universal, logger)

# Convert to pytest - this is what pytest will discover and run
test_example = to_pytest(test_example_iproxy)
```
"""
