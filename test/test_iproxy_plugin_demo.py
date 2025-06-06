"""Demonstration of tests using @injected_pytest decorator

This file shows how to write tests using the @injected_pytest decorator
for automatic pytest discovery and execution.
"""

import asyncio
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from loguru import logger

# Test design configuration
test_design = design(logger=logger)

# Module configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# Test 1: Simple sync test
@injected_pytest(test_design)
def test_sync_example(logger):
    """A simple synchronous test"""
    logger.info("Running sync test")
    assert 2 + 2 == 4


# Test 2: Async test
@injected_pytest(test_design)
async def test_async_example(logger):
    """An asynchronous test"""
    logger.info("Running async test")
    # Simulate some async work
    await asyncio.sleep(0.01)
    assert True


# Test 3: Test with injected dependency
@injected_pytest(test_design)
def test_with_string_dep(logger, storage_resolver):
    """Test that uses injected dependencies"""
    logger.info("Running test with storage_resolver dependency")
    assert hasattr(storage_resolver, "locate")
