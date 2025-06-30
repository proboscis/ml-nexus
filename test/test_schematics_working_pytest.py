"""Test working schematics_universal kinds using regular pytest

This is a simplified version that doesn't require pytest_iproxy_adapter.
"""

from test.test_schematics_working_kinds import test_working_schematics

# Re-export the test
test_working = test_working_schematics
