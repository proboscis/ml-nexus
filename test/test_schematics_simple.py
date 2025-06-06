"""Test schematics_universal with different ProjectDir kinds using @injected_pytest"""

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


# Test UV project
@injected_pytest(test_design)
async def test_uv_project(schematics_universal, logger):
    """Test UV project configuration"""
    logger.info(f"\n{'=' * 60}")
    logger.info("Testing UV kind with project: test_uv")
    logger.info(f"{'=' * 60}")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Macros count: {len(builder.macros)}")
    logger.info(f"Scripts count: {len(builder.scripts)}")

    # Verify UV-specific configuration
    scripts_str = " ".join(builder.scripts)
    assert "uv sync" in scripts_str, "UV sync command not found"
    assert builder.base_image == "python:3.11-slim"


# Test Rye project
@injected_pytest(test_design)
async def test_rye_project(schematics_universal, logger):
    """Test Rye project configuration"""
    logger.info(f"\n{'=' * 60}")
    logger.info("Testing RYE kind with project: test_rye")
    logger.info(f"{'=' * 60}")

    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Macros count: {len(builder.macros)}")
    logger.info(f"Scripts count: {len(builder.scripts)}")

    # Verify Rye-specific configuration
    scripts_str = " ".join(builder.scripts)
    assert "rye sync" in scripts_str, "Rye sync command not found"


# Test auto-detection with requirements.txt
@injected_pytest(test_design)
async def test_auto_requirements(schematics_universal, logger):
    """Test auto-detection with requirements.txt project"""
    logger.info(f"\n{'=' * 60}")
    logger.info("Testing AUTO kind with project: test_requirements")
    logger.info(f"{'=' * 60}")

    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Macros count: {len(builder.macros)}")
    logger.info(f"Scripts count: {len(builder.scripts)}")

    # Verify requirements.txt handling
    scripts_str = " ".join(builder.scripts)
    assert "pip install" in scripts_str, (
        "pip install command not found for requirements.txt"
    )


# Test source-only project
@injected_pytest(test_design)
async def test_source_project(schematics_universal, logger):
    """Test source-only project (no Python environment)"""
    logger.info(f"\n{'=' * 60}")
    logger.info("Testing SOURCE kind with project: test_source")
    logger.info(f"{'=' * 60}")

    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image="ubuntu:22.04")

    builder = schematic.builder
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Macros count: {len(builder.macros)}")
    logger.info(f"Scripts count: {len(builder.scripts)}")

    # Verify source projects have no Python setup scripts
    assert len(builder.scripts) == 0, "Source projects should have no scripts"
    assert builder.base_image == "ubuntu:22.04"


# Test all project kinds in one test
@injected_pytest(test_design)
async def test_all_project_kinds(schematics_universal, logger):
    """Test all project kinds to ensure schematics work correctly"""
    test_cases = [
        ("test_uv", "uv", "uv sync", "python:3.11-slim"),
        ("test_rye", "rye", "rye sync", "python:3.11-slim"),
        ("test_requirements", "auto", "pip install", "python:3.11-slim"),
        ("test_source", "source", None, "ubuntu:22.04"),
    ]

    for project_id, kind, expected_command, expected_base_image in test_cases:
        logger.info(f"\nTesting {kind} project: {project_id}")

        project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
        schematic = await schematics_universal(
            target=project, base_image=expected_base_image
        )

        builder = schematic.builder
        scripts_str = " ".join(builder.scripts)

        # Verify base image
        assert builder.base_image == expected_base_image, f"Wrong base image for {kind}"

        # Verify expected commands
        if expected_command:
            assert expected_command in scripts_str, (
                f"{expected_command} not found for {kind}"
            )
        else:
            assert len(builder.scripts) == 0, "Source project should have no scripts"

        logger.info(f"✓ {kind} project validated successfully")
