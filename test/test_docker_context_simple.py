"""Simple test to verify Docker context injection works correctly"""

from pinjected import IProxy, design, injected
from pinjected.test import injected_pytest
from ml_nexus import load_env_design

# Test design with zeus context
zeus_test_design = design(
    ml_nexus_docker_build_context="zeus"
)

__meta_design__ = design(
    overrides=load_env_design + zeus_test_design
)


# Simple test using injected_pytest
@injected_pytest(zeus_test_design)
async def test_docker_context_is_zeus(ml_nexus_docker_build_context, logger):
    """Test that Docker context is set to zeus"""
    logger.info(f"Docker context: {ml_nexus_docker_build_context}")
    assert ml_nexus_docker_build_context == "zeus"


# Entry point for pinjected run
@injected
async def a_verify_zeus_context(ml_nexus_docker_build_context, logger, /):
    """Verify zeus context is active"""
    logger.info(f"Current Docker build context: {ml_nexus_docker_build_context}")
    return ml_nexus_docker_build_context

verify_zeus: IProxy = a_verify_zeus_context()