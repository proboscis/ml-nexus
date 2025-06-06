"""Test to verify embedded components functionality works correctly"""

import pytest
from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
REPO_ROOT = Path(__file__).parent.parent

test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_source": TEST_PROJECT_ROOT / "test_source",
        "test_resource": TEST_PROJECT_ROOT / "test_resource",
        # For embedded tests
        "test/dummy_projects/test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test/dummy_projects/test_requirements": TEST_PROJECT_ROOT
        / "test_requirements",
        "test/dummy_projects/test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    }
)

# Test design configuration with real docker host
test_design = design(
    docker_host="local",  # Use local docker
    storage_resolver=test_storage_resolver,
    logger=logger,
    ml_nexus_default_base_image="python:3.11-slim",  # Lighter image for tests
)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


@injected_pytest(test_design)
async def test_auto_embed_uv_schematics(schematics_universal, logger):
    """Test that auto-embed UV project generates correct schematics"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])

    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Check that the schematic is generated
    assert schematic is not None
    assert schematic.builder is not None

    # Check that no cache mounts are present (embedded should have no mounts)
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    assert len(cache_mounts) == 1  # Should only have HF cache, not UV caches

    logger.info("✅ Auto-embed UV schematics test passed")


@injected_pytest(test_design)
async def test_pyvenv_embed_requirements_schematics(schematics_universal, logger):
    """Test that pyvenv-embed with requirements.txt generates correct schematics"""
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])

    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim", python_version="3.11"
    )

    # Check that the schematic is generated
    assert schematic is not None
    assert schematic.builder is not None

    # Check that no pyenv cache mounts are present
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    assert len(cache_mounts) == 1  # Should only have HF cache

    logger.info("✅ Pyvenv-embed requirements.txt schematics test passed")


@injected_pytest(test_design)
async def test_auto_embed_requirements_schematics(schematics_universal, logger):
    """Test that auto-embed with requirements.txt generates correct schematics"""
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto-embed")])

    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Check that the schematic is generated
    assert schematic is not None
    assert schematic.builder is not None

    # Check mount requests
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    assert len(cache_mounts) == 1  # Should only have HF cache

    logger.info("✅ Auto-embed requirements.txt schematics test passed")


@injected_pytest(test_design)
async def test_embedded_dockerfile_generation(schematics_universal, logger):
    """Test that embedded components generate correct Dockerfile content"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])

    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Get the Dockerfile content
    dockerfile_lines = await schematic.builder.a_get_dockerfile_lines()
    dockerfile_content = "\n".join(dockerfile_lines)

    # Check for embedded patterns
    assert "uv sync --no-install-project" in dockerfile_content  # Dependencies first
    assert "uv sync" in dockerfile_content  # Full sync after copying source

    # Check that RsyncArgs is used for copying (look for rsync pattern)
    assert any("COPY" in line or "rsync" in line.lower() for line in dockerfile_lines)

    logger.info("✅ Embedded Dockerfile generation test passed")
    logger.debug(f"Generated Dockerfile preview:\n{dockerfile_content[:500]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
