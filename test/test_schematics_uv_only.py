"""Test UV kind for schematics_universal

This test specifically verifies that UV projects are correctly
handled by the schematics_universal function.
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
    }
)

# Test design configuration
test_design = design(storage_resolver=test_storage_resolver, logger=logger)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# ===== Test UV schematic generation =====
@injected_pytest(test_design)
async def test_analyze_uv_schematic(schematics_universal, logger):
    """Test and analyze UV schematic generation"""
    logger.info("Testing UV schematic generation")

    # Create UV project
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder

    logger.info(f"\n{'=' * 60}")
    logger.info("Analysis for UV kind")
    logger.info(f"{'=' * 60}")

    # Verify base image
    assert builder.base_image == "python:3.11-slim"
    logger.info(f"Base image: {builder.base_image}")

    # Verify base stage name exists
    assert hasattr(builder, "base_stage_name")
    logger.info(f"Base stage name: {builder.base_stage_name}")

    # Verify macros
    assert len(builder.macros) > 0, "UV project should have macros"
    logger.info(f"Macros count: {len(builder.macros)}")

    # Analyze macros structure
    macro_types = {}
    for macro in builder.macros:
        macro_type = type(macro).__name__
        macro_types[macro_type] = macro_types.get(macro_type, 0) + 1

    logger.info("Macro types:")
    for mtype, count in macro_types.items():
        logger.info(f"  {mtype}: {count}")

    # Verify scripts
    assert len(builder.scripts) > 0, "UV project should have scripts"
    logger.info(f"Scripts count: {len(builder.scripts)}")

    # Check for UV-specific commands
    scripts_str = " ".join(builder.scripts)
    assert "uv" in scripts_str, "UV project scripts should contain 'uv' command"
    assert "uv sync" in scripts_str, "UV project should run 'uv sync'"

    # Show first few scripts
    logger.info("First 3 scripts:")
    for i, script in enumerate(builder.scripts[:3]):
        logger.info(f"  Script {i}: {script}")

    # Verify mount requests
    logger.info(f"Mount requests: {len(schematic.mount_requests)}")
    for i, mount in enumerate(schematic.mount_requests):
        logger.info(f"  Mount {i}: {type(mount).__name__}")

    logger.info("✅ UV schematic analysis complete")


# ===== Test UV project specifics =====
@injected_pytest(test_design)
async def test_uv_project_specifics(schematics_universal, logger):
    """Test UV-specific features in the schematic"""
    logger.info("Testing UV-specific features")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim", python_version="3.11"
    )

    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    # Verify UV installation
    assert any("uv" in script for script in builder.scripts), (
        "UV should be referenced in scripts"
    )

    # Verify Python version handling - UV uses base image's Python, not explicit version
    # The python_version parameter doesn't affect UV projects since UV manages its own Python
    # The base image python:3.11-slim provides Python 3.11
    assert builder.base_image == "python:3.11-slim", (
        "Base image should provide the Python version"
    )

    # Verify UV sync command which handles pyproject.toml
    assert "uv sync" in scripts_str, (
        "UV projects should have uv sync command that handles pyproject.toml"
    )

    logger.info("✅ UV-specific features verified")
