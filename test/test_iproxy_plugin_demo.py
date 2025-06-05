"""Demonstration that the IProxy plugin automatically discovers and runs tests

This file contains ONLY IProxy objects - no manual conversion needed!
The plugin automatically converts them to pytest functions.
"""

from pathlib import Path
from pinjected import IProxy, injected, design
from ml_nexus import load_env_design
from loguru import logger

# Module configuration
__meta_design__ = design(
    overrides=load_env_design + design(
        logger=logger
    )
)


# Test 1: Simple sync test
@injected  
def test_sync_example(logger):
    """A simple synchronous test"""
    logger.info("Running sync test")
    assert 2 + 2 == 4
    return "sync test passed"

test_sync: IProxy = test_sync_example(logger)


# Test 2: Async test
@injected
async def test_async_example(logger):
    """An asynchronous test"""
    logger.info("Running async test")
    # Simulate some async work
    await asyncio.sleep(0.01)
    assert True
    return "async test passed"

import asyncio
test_async: IProxy = test_async_example(logger)


# Test 3: Test with injected string dependency
@injected
def test_with_string_dep(logger, storage_resolver):
    """Test that uses injected dependencies"""
    logger.info("Running test with storage_resolver dependency")
    assert hasattr(storage_resolver, 'locate')
    return "deps test passed"

test_deps: IProxy = test_with_string_dep(logger, injected("storage_resolver"))


# Notice: NO manual conversion needed!
# The plugin automatically discovers these IProxy objects and runs them as tests.