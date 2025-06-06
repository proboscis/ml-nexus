"""Pytest plugin for discovering and running IProxy test objects

This plugin properly integrates with pytest's collection system to
automatically discover and run IProxy objects as test items.
"""

import pytest
from _pytest.python import Module
from pinjected import IProxy, design
from pinjected.test.injected_pytest import _to_pytest


class IProxyModule(Module):
    """Custom Module collector that handles IProxy objects"""

    def collect(self):
        """Collect test items from the module, converting IProxy objects"""
        # Get normal pytest collection, but filter out @injected functions
        from pinjected.di.partially_injected import Partial

        for item in super().collect():
            # Skip items that are Partial (injected functions)
            if hasattr(item, "obj") and isinstance(item.obj, Partial):
                continue
            yield item

        # Now look for IProxy objects that weren't collected
        module = self.obj
        module_design = getattr(module, "__meta_design__", design())
        module_file = str(self.path)

        # Find all attributes in the module
        for name in dir(module):
            # Skip if it doesn't look like a test
            if not name.startswith("test"):
                continue

            # Get the object
            obj = getattr(module, name)

            # Skip Partial objects (@injected functions)
            if isinstance(obj, Partial):
                continue

            # If it's an IProxy, convert and create a test item
            if isinstance(obj, IProxy):
                try:
                    # Convert IProxy to pytest function
                    test_func = _to_pytest(obj, module_design, module_file)

                    # Mark it as coming from IProxy
                    test_func._iproxy_original = obj
                    test_func.__name__ = name

                    # Create a pytest Function item
                    yield pytest.Function.from_parent(
                        self, name=name, callobj=test_func
                    )

                except Exception:
                    # Create a test that reports the error
                    def error_test():
                        pytest.fail(f"Failed to convert IProxy '{name}': {e}")

                    error_test.__name__ = name
                    yield pytest.Function.from_parent(
                        self, name=name, callobj=error_test
                    )


def pytest_pycollect_makeitem(collector, name, obj):
    """Hook to prevent collection of @injected functions"""
    from pinjected.di.partially_injected import Partial

    # If this is a Partial object (injected function), don't collect it
    if isinstance(obj, Partial):
        return []  # Return empty list to skip this item

    # Let pytest handle normal collection
    return None


def pytest_pycollect_makemodule(module_path, parent):
    """Replace the default module collector with our IProxy-aware version"""
    # Use our custom module collector for all Python test files
    if module_path.suffix == ".py":
        return IProxyModule.from_parent(parent, path=module_path)
    return None


def pytest_collection_modifyitems(session, config, items):
    """Add markers to IProxy tests"""
    for item in items:
        if hasattr(item.obj, "_iproxy_original"):
            item.add_marker(pytest.mark.iproxy)


def pytest_configure(config):
    """Register plugin configuration"""
    config.addinivalue_line(
        "markers", "iproxy: marks tests as converted from IProxy objects"
    )


# Optional: Add a custom report header
def pytest_report_header(config):
    """Add IProxy plugin info to pytest header"""
    return "IProxy plugin: enabled (automatic IProxy test discovery)"
