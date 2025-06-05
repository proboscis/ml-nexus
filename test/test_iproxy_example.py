"""Example of how to write pytest-compatible IProxy tests

This demonstrates the recommended pattern for creating tests with IProxy
objects that can be discovered and run by pytest.
"""

from pathlib import Path
from pinjected import IProxy, injected, design
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Import the conversion utility
from test.iproxy_test_utils import to_pytest

# Setup test project resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_source": TEST_PROJECT_ROOT / "test_source",
})

# Configure design
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)


# Step 1: Define your test as an injected function
@injected
async def a_test_uv_project(schematics_universal, logger):
    """Test UV project configuration"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Verify UV configuration
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    assert 'uv sync' in scripts_str, "UV sync command not found"
    
    logger.info(f"✅ UV project test passed")
    logger.info(f"  - Macros: {len(builder.macros)}")
    logger.info(f"  - Scripts: {len(builder.scripts)}")
    
    return True


# Step 2: Create IProxy object
test_uv_project_iproxy: IProxy = a_test_uv_project(schematics_universal, logger)

# Step 3: Convert to pytest function
test_uv_project = to_pytest(test_uv_project_iproxy)


# You can also define multiple tests in the same file
@injected
async def a_test_source_project(schematics_universal, logger):
    """Test source-only project (no Python environment)"""
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    # Verify no Python setup for source projects
    builder = schematic.builder
    assert len(builder.scripts) == 0, "Source projects should have no scripts"
    
    logger.info("✅ Source project test passed")
    return True


# Create and convert another test
test_source_project_iproxy: IProxy = a_test_source_project(schematics_universal, logger)
test_source_project = to_pytest(test_source_project_iproxy)


# Now pytest can discover and run these tests normally:
# pytest test_iproxy_example.py -v