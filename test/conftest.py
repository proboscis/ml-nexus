"""Pytest configuration for ml-nexus tests

This file configures pytest to use the IProxy plugin for discovering
and running IProxy test objects.
"""

# Enable the IProxy pytest plugin
pytest_plugins = ['test.pytest_iproxy_plugin']

# Optional: Configure pytest settings  
def pytest_configure(config):
    """Additional pytest configuration"""
    # Add custom markers or settings if needed
    pass