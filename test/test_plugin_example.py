"""Test file to demonstrate automatic IProxy test discovery

This file contains IProxy test objects that should be automatically
discovered and run by the pytest plugin without manual conversion.
"""

from pathlib import Path
from pinjected import IProxy, injected, design
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Setup test environment
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
})

__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)


# Define test as injected function
@injected
async def a_test_plugin_uv(schematics_universal, logger):
    """Test UV project via plugin"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'uv sync' in scripts_str, "UV sync command not found"
    
    logger.info("✅ Plugin UV test passed")
    return True


@injected
async def a_test_plugin_rye(schematics_universal, logger):
    """Test RYE project via plugin"""
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'rye sync' in scripts_str, "Rye sync command not found"
    
    logger.info("✅ Plugin RYE test passed")
    return True


# Create IProxy objects - NO manual conversion needed!
# The plugin should automatically discover these
test_plugin_uv: IProxy = a_test_plugin_uv(schematics_universal, logger)
test_plugin_rye: IProxy = a_test_plugin_rye(schematics_universal, logger)

# Also test with a simpler IProxy
@injected
def simple_test_function(logger):
    """Simple synchronous test"""
    logger.info("Simple test running")
    assert 1 + 1 == 2
    return "success"

test_simple: IProxy = simple_test_function(logger)