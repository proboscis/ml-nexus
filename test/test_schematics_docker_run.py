"""Test running schematics on DockerHostEnv to ensure Python is available

This test suite builds Docker images from the schematics and runs Python
commands inside the containers to verify the environments are properly set up.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Setup test project resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
})

# Test design configuration
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    docker_host="zeus",  # Required Docker host for this repo
    ml_nexus_docker_build_context="zeus",  # Use zeus Docker context for builds
)

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + test_design
)


# ===== Test UV Project Docker Run =====
@injected_pytest(test_design)
async def test_uv_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test UV project - build Docker image and verify Python is runnable"""
    logger.info("Testing UV project Docker build and Python execution")
    
    # Create schematic
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    # Note: docker_host should be configured in environment or design
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"  # Required Docker host for this repo
    )
    
    # Test 1: Run Python version command
    result = await docker_env.run_script("python --version")
    logger.info(f"Python version output: {result.stdout}")
    assert "Python" in result.stdout, f"Expected 'Python' in output, got: {result.stdout}"
    
    # Test 2: Run Python code
    result = await docker_env.run_script("python -c 'print(\"Hello from UV environment!\")'")
    logger.info(f"Python hello output: {result.stdout}")
    assert "Hello from UV environment!" in result.stdout
    
    # Test 3: Check if UV installed packages
    result = await docker_env.run_script("python -c 'import sys; print(sys.executable)'")
    logger.info(f"Python executable: {result.stdout}")
    
    logger.info("✅ UV Docker Python test passed")


# ===== Test Rye Project Docker Run =====
@injected_pytest(test_design)
async def test_rye_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test Rye project - build Docker image and verify Python is runnable"""
    logger.info("Testing Rye project Docker build and Python execution")
    
    # Create schematic
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test Python availability
    result = await docker_env.run_script("python --version")
    logger.info(f"Python version output: {result.stdout}")
    assert "Python" in result.stdout, f"Expected 'Python' in output, got: {result.stdout}"
    
    # Test Python execution
    result = await docker_env.run_script("python -c 'import platform; print(f\"Rye env: Python {platform.python_version()}\")'")
    logger.info(f"Platform info: {result.stdout}")
    assert "Rye env: Python" in result.stdout
    
    logger.info("✅ Rye Docker Python test passed")


# ===== Test Requirements.txt Project Docker Run =====
@injected_pytest(test_design)
async def test_requirements_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test requirements.txt project (via auto) - build Docker image and verify Python is runnable"""
    logger.info("Testing requirements.txt project Docker build and Python execution")
    
    # Create schematic with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test Python availability
    result = await docker_env.run_script("python --version")
    logger.info(f"Python version output: {result.stdout}")
    assert "Python" in result.stdout, f"Expected 'Python' in output, got: {result.stdout}"
    
    # Test that packages from requirements.txt are installed
    result = await docker_env.run_script("python -c 'import pandas; import numpy; print(f\"pandas {pandas.__version__}, numpy {numpy.__version__}\")'")
    logger.info(f"Package versions: {result.stdout}")
    assert "pandas" in result.stdout and "numpy" in result.stdout, f"Expected pandas and numpy versions, got: {result.stdout}"
    
    logger.info("✅ Requirements.txt Docker Python test passed")


# ===== Test Setup.py Project Docker Run =====
@injected_pytest(test_design)
async def test_setuppy_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test setup.py project (via auto) - build Docker image and verify Python is runnable"""
    logger.info("Testing setup.py project Docker build and Python execution")
    
    # Create schematic with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="auto")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test Python availability
    result = await docker_env.run_script("python --version")
    logger.info(f"Python version output: {result.stdout}")
    assert "Python" in result.stdout, f"Expected 'Python' in output, got: {result.stdout}"
    
    # Test that the package is installed
    result = await docker_env.run_script("python -c 'import test_setuppy; print(f\"test_setuppy imported successfully\")'")
    logger.info(f"Package import: {result.stdout}")
    assert "test_setuppy imported successfully" in result.stdout
    
    logger.info("✅ Setup.py Docker Python test passed")


# ===== Test Source Project (No Python) Docker Run =====
@injected_pytest(test_design)
async def test_source_docker_no_python(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test source project - build Docker image and verify no Python environment"""
    logger.info("Testing source project Docker build (should not have Python)")
    
    # Create schematic
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test that Python is NOT available (source projects don't set up Python)
    try:
        result = await docker_env.run_script("python --version")
        # If we get here, Python exists when it shouldn't
        assert False, f"Python should not be available in source project, but got: {result.stdout}"
    except Exception as e:
        # Expected - Python should not be available
        logger.info(f"Expected error (Python not found): {str(e)}")
        assert "command not found" in str(e) or "No such file" in str(e), f"Expected 'command not found' error, got: {e}"
    
    # But basic shell commands should work
    result = await docker_env.run_script("echo 'Hello from source environment'")
    logger.info(f"Echo output: {result.stdout}")
    assert "Hello from source environment" in result.stdout
    
    logger.info("✅ Source Docker (no Python) test passed")

