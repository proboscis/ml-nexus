"""Test that docker context is properly used in all docker operations"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call
import pytest
from pinjected import design, instance, injected, IProxy
from pinjected.test import injected_pytest

from ml_nexus.docker.client import LocalDockerClient, ml_nexus_default_docker_client
from ml_nexus.docker.builder.builder_utils.building import (
    build_image_with_copy,
    build_image_with_rsync,
    a_build_docker,
    a_build_docker_no_buildkit,
)
from ml_nexus.docker.builder.builder_utils.docker_contexts import a_docker_push__local


# Mock dependencies
@instance
def mock_a_system():
    """Mock a_system that tracks all commands"""
    mock = AsyncMock()
    mock.return_value = "mock output"
    return mock


@instance
def mock_logger():
    """Mock logger"""
    mock = MagicMock()
    return mock


@instance
def ml_nexus_docker_build_context():
    """Test docker context"""
    return "test-context"


@instance
def ml_nexus_debug_docker_build():
    return False


@instance
def mock_a_setup_docker_credentials():
    """Mock docker credentials setup"""
    return AsyncMock()


# Test design
test_design = design(
    a_system=mock_a_system,
    logger=mock_logger,
    ml_nexus_docker_build_context=ml_nexus_docker_build_context,
    ml_nexus_debug_docker_build=ml_nexus_debug_docker_build,
    a_setup_docker_credentials=mock_a_setup_docker_credentials,
)


@injected_pytest(test_design)
async def test_local_docker_client_uses_context(new_LocalDockerClient, mock_a_system):
    """Test that LocalDockerClient properly uses docker context"""
    client = new_LocalDockerClient()
    
    # Test run_container
    await client.run_container("test-image", "echo hello", ["-d"])
    mock_a_system.assert_called_with("docker --context test-context run -d test-image echo hello")
    
    # Test exec_container
    await client.exec_container("test-container", "ls -la")
    mock_a_system.assert_called_with("docker --context test-context exec test-container ls -la")
    
    # Test build_image
    await client.build_image(Path("/tmp/context"), "test:latest", ["-f", "Dockerfile"])
    mock_a_system.assert_called_with("docker --context test-context build -f Dockerfile -t test:latest /tmp/context")
    
    # Test push_image
    await client.push_image("test:latest")
    mock_a_system.assert_called_with("docker --context test-context push test:latest")
    
    # Test stop_container
    await client.stop_container("test-container")
    mock_a_system.assert_called_with("docker --context test-context stop test-container")


@injected_pytest(test_design)
async def test_docker_build_functions_use_context(mock_a_system):
    """Test that docker build functions use context"""
    
    # Test a_build_docker
    await a_build_docker(
        tag="test:latest",
        context_dir="/tmp/context",
        options="--no-cache",
        push=True
    )
    
    # Verify build command uses context
    assert any("docker --context test-context build" in str(call) for call in mock_a_system.call_args_list)
    # Verify push command uses context
    assert any("docker --context test-context push" in str(call) for call in mock_a_system.call_args_list)
    
    # Reset mock
    mock_a_system.reset_mock()
    
    # Test a_build_docker_no_buildkit
    await a_build_docker_no_buildkit(
        tag="test:latest",
        context_dir="/tmp/context",
        options="--no-cache",
        push=True
    )
    
    # Verify commands use context
    assert any("docker --context test-context build" in str(call) for call in mock_a_system.call_args_list)
    assert any("docker --context test-context push" in str(call) for call in mock_a_system.call_args_list)


@injected_pytest(test_design)
async def test_docker_push_local_uses_context(mock_a_system, mock_a_setup_docker_credentials):
    """Test that a_docker_push__local uses context"""
    
    await a_docker_push__local(tag="test:latest")
    
    # Verify credentials were set up
    mock_a_setup_docker_credentials.assert_called_once_with("test:latest")
    
    # Verify push command uses context
    mock_a_system.assert_called_with("docker --context test-context push test:latest")


@injected_pytest(test_design)
async def test_build_image_with_copy_uses_context(mock_a_system):
    """Test that build_image_with_copy uses context"""
    
    await build_image_with_copy(
        from_image="ubuntu:22.04",
        pre_copy_commands="RUN apt-get update",
        post_copy_commands="RUN echo done",
        docker_resource_paths={},
        tag="test:latest",
        push=True
    )
    
    # Check that both build and push use context
    calls = [str(call) for call in mock_a_system.call_args_list]
    assert any("docker --context test-context build" in call for call in calls)
    assert any("docker --context test-context push" in call for call in calls)


@injected_pytest(test_design)
async def test_build_image_with_rsync_uses_context(mock_a_system):
    """Test that build_image_with_rsync uses context"""
    
    dockerfile_content = """
FROM ubuntu:22.04
RUN echo "Hello World"
"""
    
    await build_image_with_rsync(
        code=dockerfile_content,
        tag="test:latest",
        push=True
    )
    
    # Check that build, history, and push commands use context
    calls = [str(call) for call in mock_a_system.call_args_list]
    assert any("docker --context test-context build" in call for call in calls)
    assert any("docker --context test-context history" in call for call in calls)
    assert any("docker --context test-context push" in call for call in calls)


# Test with empty context to ensure it still works
empty_context_design = design(
    a_system=mock_a_system,
    logger=mock_logger,
    ml_nexus_docker_build_context="",  # Empty context
    ml_nexus_debug_docker_build=ml_nexus_debug_docker_build,
)


@injected_pytest(empty_context_design)
async def test_docker_operations_with_empty_context(new_LocalDockerClient, mock_a_system):
    """Test that docker operations work correctly with empty context"""
    client = new_LocalDockerClient()
    
    # Test run_container - should use plain docker command
    await client.run_container("test-image", "echo hello")
    mock_a_system.assert_called_with("docker run test-image echo hello")
    
    # Test push_image - should use plain docker command
    await client.push_image("test:latest")
    mock_a_system.assert_called_with("docker push test:latest")


# IProxy entry points for testing with pinjected
test_local_docker_client: IProxy = test_local_docker_client_uses_context()
test_build_functions: IProxy = test_docker_build_functions_use_context()
test_push_local: IProxy = test_docker_push_local_uses_context()
test_copy_build: IProxy = test_build_image_with_copy_uses_context()
test_rsync_build: IProxy = test_build_image_with_rsync_uses_context()
test_empty_context: IProxy = test_docker_operations_with_empty_context()


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v"])