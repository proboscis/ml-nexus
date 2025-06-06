"""Example of how to write tests with @injected_pytest decorator

This demonstrates the recommended pattern for creating tests using
the @injected_pytest decorator that can be discovered and run by pytest.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Setup test project resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_source": TEST_PROJECT_ROOT / "test_source",
})

# Test design configuration
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger
)

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + test_design
)


@injected_pytest(test_design)
async def test_uv_project(schematics_universal, logger):
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
    
    logger.info("✅ UV project test passed")
    logger.info(f"  - Macros: {len(builder.macros)}")
    logger.info(f"  - Scripts: {len(builder.scripts)}")


@injected_pytest(test_design)
async def test_source_project(schematics_universal, logger):
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


# Now pytest can discover and run these tests normally:
# pytest test_iproxy_example.py -v