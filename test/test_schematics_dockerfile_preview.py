"""Test Dockerfile generation for different ProjectDir kinds

This test verifies that correct Dockerfiles are generated for
each type of project (source, resource, uv, rye, etc).
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

_storage_resolver = StaticStorageResolver(
    {
        "test_source": TEST_PROJECT_ROOT / "test_source",
        "test_resource": TEST_PROJECT_ROOT / "test_resource",
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    }
)

# Test design configuration
_design = load_env_design + design(
    storage_resolver=_storage_resolver, 
    logger=logger
)


# ===== Test 1: Source kind Dockerfile =====
@injected_pytest(_design)
async def test_source_dockerfile_generation(schematics_universal, logger):
    """Test Dockerfile generation for source kind"""
    logger.info("Testing source kind Dockerfile generation")

    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_source", kind="source")]),
        base_image="ubuntu:22.04",
    )

    dockerfile = schematic.builder.dockerfile

    # Verify basic structure
    assert "FROM ubuntu:22.04" in dockerfile
    assert "python" not in dockerfile.lower(), "Source kind should not set up Python"

    logger.info("✅ Source Dockerfile verified")


# ===== Test 2: UV kind Dockerfile =====
@injected_pytest(_design)
async def test_uv_dockerfile_generation(schematics_universal, logger):
    """Test Dockerfile generation for UV kind"""
    logger.info("Testing UV kind Dockerfile generation")

    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")]),
        base_image="python:3.11-slim",
    )

    dockerfile = schematic.builder.dockerfile

    # Verify UV-specific content
    assert "FROM python:3.11-slim" in dockerfile
    assert "uv" in dockerfile.lower(), "UV kind should reference uv tool"
    assert "pyproject.toml" in dockerfile, "UV projects use pyproject.toml"

    logger.info("✅ UV Dockerfile verified")


# ===== Test 3: Rye kind Dockerfile =====
@injected_pytest(_design)
async def test_rye_dockerfile_generation(schematics_universal, logger):
    """Test Dockerfile generation for Rye kind"""
    logger.info("Testing Rye kind Dockerfile generation")

    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")]),
        base_image="python:3.11-slim",
    )

    dockerfile = schematic.builder.dockerfile

    # Verify Rye-specific content
    assert "FROM python:3.11-slim" in dockerfile
    assert "rye" in dockerfile.lower(), "Rye kind should reference rye tool"

    logger.info("✅ Rye Dockerfile verified")


# ===== Test 4: Setup.py kind Dockerfile =====
@injected_pytest(_design)
async def test_setuppy_dockerfile_generation(schematics_universal, logger):
    """Test Dockerfile generation for setup.py kind"""
    logger.info("Testing setup.py kind Dockerfile generation")

    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_setuppy", kind="setup.py")]),
        base_image="python:3.11-slim",
        python_version="3.11",
    )

    dockerfile = schematic.builder.dockerfile

    # Verify setup.py-specific content
    assert "FROM python:3.11-slim" in dockerfile
    assert "pip" in dockerfile, "Setup.py projects should use pip"
    assert "setup.py" in dockerfile or "-e ." in dockerfile, "Should install package"

    logger.info("✅ Setup.py Dockerfile verified")


# ===== Test 5: Mixed project Dockerfile =====
@injected_pytest(_design)
async def test_mixed_dockerfile_generation(schematics_universal, logger):
    """Test Dockerfile generation for mixed project kinds"""
    logger.info("Testing mixed kinds Dockerfile generation")

    schematic = await schematics_universal(
        target=ProjectDef(
            dirs=[
                ProjectDir("test_uv", kind="uv"),
                ProjectDir("test_resource", kind="resource"),
                ProjectDir("test_source", kind="source"),
            ]
        ),
        base_image="python:3.11-slim",
    )

    dockerfile = schematic.builder.dockerfile

    # Verify it handles multiple kinds
    assert "FROM python:3.11-slim" in dockerfile
    assert len(dockerfile) > 100, "Mixed project should generate substantial Dockerfile"

    # Log first part of dockerfile for inspection
    logger.info("Mixed Dockerfile preview:")
    logger.info(dockerfile[:500] + "...")

    logger.info("✅ Mixed Dockerfile verified")


# ===== Test 6: Print source dockerfile =====
@injected_pytest(_design)
async def test_print_source_dockerfile(schematics_universal, logger):
    """Print and verify source kind Dockerfile"""
    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_source", kind="source")]),
        base_image="ubuntu:22.04",
    )
    
    dockerfile = schematic.builder.dockerfile
    
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Dockerfile for SOURCE kind")
    logger.info(f"{'=' * 60}")
    logger.info(f"\n{dockerfile}\n")
    
    assert dockerfile is not None
    assert len(dockerfile) > 0


# ===== Test 7: Print UV dockerfile =====
@injected_pytest(_design)
async def test_print_uv_dockerfile(schematics_universal, logger):
    """Print and verify UV kind Dockerfile"""
    schematic = await schematics_universal(
        target=ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")]),
        base_image="python:3.11-slim",
    )
    
    dockerfile = schematic.builder.dockerfile
    
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Dockerfile for UV kind")
    logger.info(f"{'=' * 60}")
    logger.info(f"\n{dockerfile}\n")
    
    assert dockerfile is not None
    assert len(dockerfile) > 0