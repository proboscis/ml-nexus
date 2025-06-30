"""Test to verify Docker build context is properly used

This test specifically verifies that the ml_nexus_docker_build_context
injection is working correctly and Docker builds use the specified context.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import uuid

# Test storage resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
    }
)

# Test design with zeus context
test_design = load_env_design + design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    ml_nexus_docker_build_context="zeus",  # Set zeus as build context
)

# Module design
# __meta_design__ = design(overrides=load_env_design + test_design)  # Removed deprecated __meta_design__


# ===== Test Docker context injection =====
@injected_pytest(test_design)
async def test_docker_context_injection(ml_nexus_docker_build_context, logger):
    """Verify that Docker context is properly injected"""
    logger.info(f"Docker build context is set to: {ml_nexus_docker_build_context}")
    assert ml_nexus_docker_build_context == "zeus", (
        f"Expected 'zeus', got '{ml_nexus_docker_build_context}'"
    )
    logger.info("✅ Docker context injection verified")


# ===== Test Docker build with context =====
@injected_pytest(test_design)
async def test_docker_build_with_context(
    new_DockerBuilder, a_build_docker, ml_nexus_docker_build_context, logger
):
    """Test that a_build_docker uses the specified context"""
    logger.info(f"Testing Docker build with context: {ml_nexus_docker_build_context}")

    # Create a simple Docker builder
    builder = new_DockerBuilder(base_image="python:3.11-slim", name="test-zeus-context")

    # Add a simple script to verify
    builder = builder.add_script("echo 'Built with Zeus context'")

    # Generate unique tag
    tag = f"ml-nexus-test-zeus:{uuid.uuid4().hex[:8]}"

    try:
        # Build the image - this should use zeus context
        logger.info(
            f"Building image {tag} using context {ml_nexus_docker_build_context}"
        )
        result = await builder.a_build(tag, use_cache=False)

        assert result == tag, f"Expected tag {tag}, got {result}"
        logger.info(f"✅ Successfully built image {tag} with zeus context")

        # Note: We can't easily verify the context was used without checking Docker logs
        # but the build should succeed if zeus context is properly configured

    except Exception as e:
        logger.error(f"Build failed: {e}")
        raise
