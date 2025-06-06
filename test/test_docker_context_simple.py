"""Simple test to verify docker context is working"""

import os
import subprocess
import tempfile
from pathlib import Path


def test_docker_context_in_build():
    """Test that docker build commands use the configured context"""
    
    # Set up a test context
    os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"] = "test-context"
    
    # Create a simple test that uses pinjected to check docker commands
    test_script = '''
from pinjected import IProxy, injected
from ml_nexus.docker.builder.builder_utils.building import a_build_docker

# Create a mock a_system to capture commands
captured_commands = []

@injected
async def mock_a_system(cmd: str):
    captured_commands.append(cmd)
    return ""

# Override a_system with our mock
from ml_nexus import load_env_design
import pinjected

test_design = load_env_design + pinjected.design(
    a_system=mock_a_system
)

# Test the build function
async def test_build():
    resolver = test_design.to_resolver()
    build_func = await resolver.provide(a_build_docker)
    
    # Call build with push=True
    await build_func(
        tag="test:latest",
        context_dir="/tmp/test",
        options="",
        push=True
    )
    
    # Check captured commands
    for cmd in captured_commands:
        print(f"Command: {cmd}")
    
    # Verify context is used
    build_with_context = any("docker --context test-context build" in cmd for cmd in captured_commands)
    push_with_context = any("docker --context test-context push" in cmd for cmd in captured_commands)
    
    print(f"Build uses context: {build_with_context}")
    print(f"Push uses context: {push_with_context}")
    
    assert build_with_context, f"Build command should use context. Commands: {captured_commands}"
    assert push_with_context, f"Push command should use context. Commands: {captured_commands}"

# Run the test
import asyncio
asyncio.run(test_build())
print("✓ Docker context test passed!")
'''

    # Write test script to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        test_file = f.name
    
    try:
        # Run the test script
        result = subprocess.run(
            ['uv', 'run', 'python', test_file],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check result
        assert result.returncode == 0, f"Test failed with return code {result.returncode}"
        assert "✓ Docker context test passed!" in result.stdout
        
    finally:
        # Clean up
        os.unlink(test_file)
        if "ML_NEXUS_DOCKER_BUILD_CONTEXT" in os.environ:
            del os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"]


def test_docker_client_context():
    """Test that LocalDockerClient uses context"""
    
    # Set context
    os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"] = "client-test-context"
    
    test_script = '''
from ml_nexus.docker.client import LocalDockerClient
import asyncio

# Create client with test context
client = LocalDockerClient(
    _a_system=lambda cmd: print(f"EXEC: {cmd}"),
    _logger=lambda: None,
    _ml_nexus_docker_build_context="client-test-context"
)

# Test commands
asyncio.run(client.push_image("test:latest"))
'''

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        test_file = f.name
    
    try:
        result = subprocess.run(
            ['uv', 'run', 'python', test_file],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        print("Client test output:", result.stdout)
        
        # Check that context is used
        assert "docker --context client-test-context push" in result.stdout
        
    finally:
        os.unlink(test_file)
        if "ML_NEXUS_DOCKER_BUILD_CONTEXT" in os.environ:
            del os.environ["ML_NEXUS_DOCKER_BUILD_CONTEXT"]


if __name__ == "__main__":
    print("Testing docker context usage...")
    
    print("\n1. Testing docker build/push with context:")
    test_docker_context_in_build()
    
    print("\n2. Testing LocalDockerClient with context:")
    test_docker_client_context()
    
    print("\n✅ All tests passed!")