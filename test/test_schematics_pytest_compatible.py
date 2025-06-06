"""Test schematics with different ProjectDir kinds using @injected_pytest

This demonstrates the standard pattern for writing tests with the
@injected_pytest decorator.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_source": TEST_PROJECT_ROOT / "test_source",
        "test_resource": TEST_PROJECT_ROOT / "test_resource",
    }
)

# Test design configuration
test_design = design(storage_resolver=test_storage_resolver, logger=logger)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# Test UV project kind
@injected_pytest(test_design)
async def test_uv_kind(schematics_universal, logger):
    """Test UV ProjectDir kind"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    assert "uv sync" in scripts_str, "UV sync command not found"
    assert builder.base_image == "python:3.11-slim"
    logger.info(f"✓ UV test passed - found {len(builder.scripts)} scripts")


# Test Rye project kind
@injected_pytest(test_design)
async def test_rye_kind(schematics_universal, logger):
    """Test RYE ProjectDir kind"""
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    assert "rye sync" in scripts_str, "Rye sync command not found"
    assert builder.base_image == "python:3.11-slim"
    logger.info(f"✓ RYE test passed - found {len(builder.scripts)} scripts")


# Test auto-detection with setup.py
@injected_pytest(test_design)
async def test_auto_setuppy(schematics_universal, logger):
    """Test auto-detection with setup.py project"""
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="auto")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    assert "pip install -e ." in scripts_str, "pip install -e . not found for setup.py"
    logger.info("✓ Auto-detection (setup.py) test passed")


# Now pytest can discover and run these tests normally!
# Run with: pytest test_schematics_pytest_compatible.py
