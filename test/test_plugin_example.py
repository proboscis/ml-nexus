"""Test file for plugin functionality with schematics

This file tests various project types using the plugin system
with proper @injected_pytest decorators.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Setup test environment
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
})

# Test design configuration
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger
)

__meta_design__ = design(
    overrides=load_env_design + test_design
)


# ===== Test 1: UV project plugin =====
@injected_pytest(test_design)
async def test_plugin_uv(schematics_universal, logger):
    """Test UV project via plugin"""
    logger.info("Testing UV project plugin")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'uv sync' in scripts_str, "UV sync command not found"
    
    logger.info("✅ Plugin UV test passed")


# ===== Test 2: RYE project plugin =====
@injected_pytest(test_design)
async def test_plugin_rye(schematics_universal, logger):
    """Test RYE project via plugin"""
    logger.info("Testing RYE project plugin")
    
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'rye sync' in scripts_str, "Rye sync command not found"
    
    logger.info("✅ Plugin RYE test passed")


# ===== Test 3: Simple synchronous test =====
@injected_pytest(test_design)
def test_simple(logger):
    """Simple synchronous test"""
    logger.info("Simple test running")
    assert 1 + 1 == 2
    logger.info("✅ Simple test passed")