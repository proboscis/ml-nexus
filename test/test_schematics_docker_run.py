"""Test running schematics on DockerHostEnv to ensure Python is available

This test suite builds Docker images from the schematics and runs Python
commands inside the containers to verify the environments are properly set up.
"""

from pathlib import Path
from pinjected import IProxy, injected, design
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from loguru import logger

# Import the conversion utility for pytest
from test.iproxy_test_utils import to_pytest

# Setup test project resolver
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
})

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)


# ===== Test UV Project Docker Run =====
@injected
async def a_test_uv_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger):
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
        docker_host="localhost"  # This should be configured based on your setup
    )
    
    try:
        # Test 1: Run Python version command
        result = await docker_env.run_script("python --version")
        logger.info(f"Python version output: {result}")
        assert "Python" in result, f"Expected 'Python' in output, got: {result}"
        
        # Test 2: Run Python code
        result = await docker_env.run_script("python -c 'print(\"Hello from UV environment!\")'")
        logger.info(f"Python hello output: {result}")
        assert "Hello from UV environment!" in result
        
        # Test 3: Check if UV installed packages
        result = await docker_env.run_script("python -c 'import sys; print(sys.executable)'")
        logger.info(f"Python executable: {result}")
        
        logger.info("✅ UV Docker Python test passed")
        return True
        
    finally:
        # Note: DockerEnvFromSchematics doesn't have a_cleanup method
        # Containers are ephemeral and cleaned up after run_script
        pass

test_uv_docker_python_iproxy: IProxy = a_test_uv_docker_python(schematics_universal, new_DockerEnvFromSchematics, logger)
test_uv_docker_python = to_pytest(test_uv_docker_python_iproxy)


# ===== Test Rye Project Docker Run =====
@injected
async def a_test_rye_docker_python(schematics_universal, DockerHostEnv, logger):
    """Test Rye project - build Docker image and verify Python is runnable"""
    logger.info("Testing Rye project Docker build and Python execution")
    
    # Create schematic
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = await DockerHostEnv.a_from_schematics(schematic)
    
    try:
        # Test Python availability
        result = await docker_env.a_run_script("python --version")
        logger.info(f"Python version output: {result}")
        assert "Python" in result, f"Expected 'Python' in output, got: {result}"
        
        # Test Python execution
        result = await docker_env.a_run_script("python -c 'import platform; print(f\"Rye env: Python {platform.python_version()}\")'")
        logger.info(f"Platform info: {result}")
        assert "Rye env: Python" in result
        
        logger.info("✅ Rye Docker Python test passed")
        return True
        
    finally:
        await docker_env.a_cleanup()

test_rye_docker_python_iproxy: IProxy = a_test_rye_docker_python(schematics_universal, DockerHostEnv, logger)
test_rye_docker_python = to_pytest(test_rye_docker_python_iproxy)


# ===== Test Requirements.txt Project Docker Run =====
@injected
async def a_test_requirements_docker_python(schematics_universal, DockerHostEnv, logger):
    """Test requirements.txt project (via auto) - build Docker image and verify Python is runnable"""
    logger.info("Testing requirements.txt project Docker build and Python execution")
    
    # Create schematic with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = await DockerHostEnv.a_from_schematics(schematic)
    
    try:
        # Test Python availability
        result = await docker_env.a_run_script("python --version")
        logger.info(f"Python version output: {result}")
        assert "Python" in result, f"Expected 'Python' in output, got: {result}"
        
        # Test that packages from requirements.txt are installed
        result = await docker_env.a_run_script("python -c 'import pandas; import numpy; print(f\"pandas {pandas.__version__}, numpy {numpy.__version__}\")'")
        logger.info(f"Package versions: {result}")
        assert "pandas" in result and "numpy" in result, f"Expected pandas and numpy versions, got: {result}"
        
        logger.info("✅ Requirements.txt Docker Python test passed")
        return True
        
    finally:
        await docker_env.a_cleanup()

test_requirements_docker_python_iproxy: IProxy = a_test_requirements_docker_python(schematics_universal, DockerHostEnv, logger)
test_requirements_docker_python = to_pytest(test_requirements_docker_python_iproxy)


# ===== Test Setup.py Project Docker Run =====
@injected
async def a_test_setuppy_docker_python(schematics_universal, DockerHostEnv, logger):
    """Test setup.py project (via auto) - build Docker image and verify Python is runnable"""
    logger.info("Testing setup.py project Docker build and Python execution")
    
    # Create schematic with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="auto")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    docker_env = await DockerHostEnv.a_from_schematics(schematic)
    
    try:
        # Test Python availability
        result = await docker_env.a_run_script("python --version")
        logger.info(f"Python version output: {result}")
        assert "Python" in result, f"Expected 'Python' in output, got: {result}"
        
        # Test that the package is installed
        result = await docker_env.a_run_script("python -c 'import test_setuppy; print(f\"test_setuppy imported successfully\")'")
        logger.info(f"Package import: {result}")
        assert "test_setuppy imported successfully" in result
        
        logger.info("✅ Setup.py Docker Python test passed")
        return True
        
    finally:
        await docker_env.a_cleanup()

test_setuppy_docker_python_iproxy: IProxy = a_test_setuppy_docker_python(schematics_universal, DockerHostEnv, logger)
test_setuppy_docker_python = to_pytest(test_setuppy_docker_python_iproxy)


# ===== Test Source Project (No Python) Docker Run =====
@injected
async def a_test_source_docker_no_python(schematics_universal, DockerHostEnv, logger):
    """Test source project - build Docker image and verify no Python environment"""
    logger.info("Testing source project Docker build (should not have Python)")
    
    # Create schematic
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    # Create Docker environment
    docker_env = await DockerHostEnv.a_from_schematics(schematic)
    
    try:
        # Test that Python is NOT available (source projects don't set up Python)
        try:
            result = await docker_env.a_run_script("python --version")
            # If we get here, Python exists when it shouldn't
            assert False, f"Python should not be available in source project, but got: {result}"
        except Exception as e:
            # Expected - Python should not be available
            logger.info(f"Expected error (Python not found): {str(e)}")
            assert "command not found" in str(e) or "No such file" in str(e), f"Expected 'command not found' error, got: {e}"
        
        # But basic shell commands should work
        result = await docker_env.a_run_script("echo 'Hello from source environment'")
        logger.info(f"Echo output: {result}")
        assert "Hello from source environment" in result
        
        logger.info("✅ Source Docker (no Python) test passed")
        return True
        
    finally:
        await docker_env.a_cleanup()

test_source_docker_no_python_iproxy: IProxy = a_test_source_docker_no_python(schematics_universal, DockerHostEnv, logger)
test_source_docker_no_python = to_pytest(test_source_docker_no_python_iproxy)


# ===== Test All Projects in Sequence =====
@injected
async def a_test_all_docker_python(
    a_test_uv_docker_python,
    a_test_rye_docker_python,
    a_test_requirements_docker_python,
    a_test_setuppy_docker_python,
    a_test_source_docker_no_python,
    logger
):
    """Run all Docker Python tests in sequence"""
    logger.info("Running all Docker Python environment tests...")
    
    tests = [
        ("UV", a_test_uv_docker_python),
        ("Rye", a_test_rye_docker_python),
        ("Requirements.txt", a_test_requirements_docker_python),
        ("Setup.py", a_test_setuppy_docker_python),
        ("Source (no Python)", a_test_source_docker_no_python),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            logger.info(f"\n{'='*60}\nRunning {name} test...\n{'='*60}")
            await test_func()
            results.append(f"✅ {name}")
        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")
            results.append(f"❌ {name}: {str(e)}")
    
    logger.info("\n" + "="*60)
    logger.info("SUMMARY:")
    for result in results:
        logger.info(result)
    
    # Check if all passed
    failed = [r for r in results if "❌" in r]
    if failed:
        raise AssertionError(f"Some tests failed: {failed}")
    
    return "All Docker Python tests passed!"

test_all_docker_python_iproxy: IProxy = a_test_all_docker_python(
    a_test_uv_docker_python,
    a_test_rye_docker_python,
    a_test_requirements_docker_python,
    a_test_setuppy_docker_python,
    a_test_source_docker_no_python,
    logger
)
test_all_docker_python = to_pytest(test_all_docker_python_iproxy)