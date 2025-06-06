"""Integration test to verify docker context is being used"""

from pinjected import design, instance
from pinjected.test import injected_pytest
from unittest.mock import AsyncMock
import pytest


# Mock a_system to capture docker commands
@instance
def mock_a_system():
    mock = AsyncMock()
    mock.return_value = ""
    return mock


# Test design with docker context
test_design = design(
    a_system=mock_a_system, ml_nexus_docker_build_context="zeus-context"
)


@injected_pytest(test_design)
async def test_docker_client_integration(
    ml_nexus_default_docker_client, mock_a_system, logger
):
    """Test that docker client uses context in commands"""
    # Get the docker client
    client = ml_nexus_default_docker_client

    # Test various operations
    await client.run_container("ubuntu:22.04", "echo hello")
    await client.push_image("myimage:latest")

    # Check that context was used
    calls = [str(call) for call in mock_a_system.call_args_list]

    # Verify docker commands include context
    assert any("docker --context zeus-context run" in call for call in calls), (
        f"Context not found in run command. Calls: {calls}"
    )
    assert any("docker --context zeus-context push" in call for call in calls), (
        f"Context not found in push command. Calls: {calls}"
    )

    logger.info("Docker context integration test passed!")


@injected_pytest(test_design)
async def test_build_operations_with_context(a_build_docker, mock_a_system, logger):
    """Test that build operations use docker context"""
    # Test docker build with push
    await a_build_docker(
        tag="test:latest", context_dir="/tmp/test", options="", push=True
    )

    # Check commands
    calls = [str(call) for call in mock_a_system.call_args_list]

    # Verify both build and push use context
    assert any("docker --context zeus-context build" in call for call in calls), (
        f"Context not found in build. Calls: {calls}"
    )
    assert any("docker --context zeus-context push" in call for call in calls), (
        f"Context not found in push. Calls: {calls}"
    )

    logger.info("Build operations context test passed!")


# Simple direct test of docker context usage
def test_docker_context_env_var():
    """Test that ML_NEXUS_DOCKER_BUILD_CONTEXT env var is properly used"""
    import os

    # Set the env var
    os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"] = "test-env-context"

    # Import and check the design loads it
    from ml_nexus import load_env_design

    design_instance = load_env_design()

    # The context should be loaded from env
    graph = design_instance.to_graph()
    context = graph.get("ml_nexus_docker_build_context")

    assert context == "test-env-context", f"Expected 'test-env-context', got {context}"

    # Clean up
    del os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"]
    print("Environment variable test passed!")


if __name__ == "__main__":
    # Run the env var test
    test_docker_context_env_var()

    # Run pytest for async tests
    pytest.main([__file__, "-v", "-k", "test_docker"])
