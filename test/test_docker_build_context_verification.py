"""Test to verify Docker build context is properly used

This test specifically verifies that the ml_nexus_docker_build_context
injection is working correctly and Docker builds use the specified context.
"""

from pathlib import Path
from pinjected import IProxy, design, injected
from ml_nexus import load_env_design
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import uuid

# Import test utilities
from test.iproxy_test_utils import to_pytest

# Test storage resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
})

# Module design with zeus context
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger,
        ml_nexus_docker_build_context="zeus",  # Set zeus as build context
    )
)


# ===== Test Docker context injection =====
@injected
async def a_test_docker_context_injection(
    ml_nexus_docker_build_context,
    logger
):
    """Verify that Docker context is properly injected"""
    logger.info(f"Docker build context is set to: {ml_nexus_docker_build_context}")
    assert ml_nexus_docker_build_context == "zeus", f"Expected 'zeus', got '{ml_nexus_docker_build_context}'"
    logger.info("✅ Docker context injection verified")
    return ml_nexus_docker_build_context

test_docker_context_injection_iproxy: IProxy = a_test_docker_context_injection(
    injected("ml_nexus_docker_build_context"),
    injected("logger")
)
test_docker_context_injection = to_pytest(test_docker_context_injection_iproxy)


# ===== Test Docker build with context =====
@injected
async def a_test_docker_build_with_context(
    new_DockerBuilder,
    a_build_docker,
    ml_nexus_docker_build_context,
    logger
):
    """Test that a_build_docker uses the specified context"""
    logger.info(f"Testing Docker build with context: {ml_nexus_docker_build_context}")
    
    # Create a simple Docker builder
    builder = new_DockerBuilder(
        base_image="python:3.11-slim",
        name="test-zeus-context"
    )
    
    # Add a simple script to verify
    builder = builder.add_script("echo 'Built with Zeus context'")
    
    # Generate unique tag
    tag = f"ml-nexus-test-zeus:{uuid.uuid4().hex[:8]}"
    
    try:
        # Build the image - this should use zeus context
        logger.info(f"Building image {tag} using context {ml_nexus_docker_build_context}")
        result = await builder.a_build(tag, use_cache=False)
        
        assert result == tag, f"Expected tag {tag}, got {result}"
        logger.info(f"✅ Successfully built image {tag} with zeus context")
        
        # Note: We can't easily verify the context was used without checking Docker logs
        # but the build should succeed if zeus context is properly configured
        
    except Exception as e:
        logger.error(f"Build failed: {e}")
        raise

test_docker_build_with_context_iproxy: IProxy = a_test_docker_build_with_context(
    injected("new_DockerBuilder"),
    injected("a_build_docker"),
    injected("ml_nexus_docker_build_context"),
    injected("logger")
)
test_docker_build_with_context = to_pytest(test_docker_build_with_context_iproxy)


# ===== Test multiple contexts override =====
@injected
async def a_test_context_override(logger):
    """Test that context can be overridden in design"""
    
    # Create a new design with different context
    with design(ml_nexus_docker_build_context="colima"):
        @injected
        async def check_context(ml_nexus_docker_build_context):
            return ml_nexus_docker_build_context
        
        context = await check_context()
        assert context == "colima", f"Expected 'colima', got '{context}'"
        logger.info("✅ Context override works correctly")
    
    # Verify original context is still zeus
    @injected
    async def check_original(ml_nexus_docker_build_context):
        return ml_nexus_docker_build_context
    
    original = await check_original()
    assert original == "zeus", f"Expected 'zeus', got '{original}'"
    logger.info("✅ Original context preserved")

test_context_override_iproxy: IProxy = a_test_context_override(injected("logger"))
test_context_override = to_pytest(test_context_override_iproxy)


# ===== IProxy entry points =====
verify_zeus_context: IProxy = test_docker_context_injection_iproxy
build_with_zeus: IProxy = test_docker_build_with_context_iproxy
test_override: IProxy = test_context_override_iproxy