"""Test embedded components by actually running Python scripts in Docker containers"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    }
)

# Test design configuration
_design = load_env_design + design(
    storage_resolver=_storage_resolver,
    logger=logger,
    ml_nexus_default_base_image="python:3.11-slim",
    docker_host="local",  # Use local Docker
)


# Test 1: Auto-embed UV project
@injected_pytest(_design)
async def test_uv_auto_embed_schematic(schematics_universal, logger):
    """Test UV auto-embed schematic generation"""
    logger.info("Testing UV auto-embed schematic generation")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    assert schematic is not None
    assert schematic.builder is not None
    
    logger.info("✅ UV auto-embed schematic created successfully")


@injected_pytest(_design)
async def test_uv_auto_embed_docker_run(
    schematics_universal,
    a_PersistentDockerEnvFromSchematics,
    logger
):
    """Test UV auto-embed Docker container with Python execution"""
    logger.info("Testing UV auto-embed Docker container")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="local",
        container_name="test_embed_uv",
    )
    
    # Start container
    await docker_env.start()
    
    try:
        # Run Python script to verify UV dependencies
        result = await docker_env.run_script("""
echo "=== Testing UV auto-embed project ==="
python --version
echo "--- Checking UV installation ---"
which uv || echo "UV not found"
uv --version || echo "UV command failed"
echo "--- Testing Python imports ---"
python -c "
import sys
print(f'Python path: {sys.executable}')
print('Testing embedded dependencies:')
try:
    import requests
    print(f'✓ requests {requests.__version__}')
except ImportError as e:
    print(f'✗ requests import failed: {e}')
try:
    import pydantic
    print(f'✓ pydantic {pydantic.__version__}')
except ImportError as e:
    print(f'✗ pydantic import failed: {e}')
"
echo "--- Running project main.py ---"
cd /sources/test_uv
python main.py || echo "main.py execution failed"
        """)
        
        logger.info(f"Test result:\n{result}")
        
        # Verify the test ran successfully
        assert result is not None
        assert "✓ requests" in result
        assert "✓ pydantic" in result
        
    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 2: Pyvenv-embed with requirements.txt
@injected_pytest(_design)
async def test_pyvenv_embed_schematic(schematics_universal, logger):
    """Test pyvenv-embed schematic generation"""
    logger.info("Testing pyvenv-embed schematic generation")
    
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])
    schematic = await schematics_universal(target=project, python_version="3.11")
    
    assert schematic is not None
    assert schematic.builder is not None
    
    logger.info("✅ Pyvenv-embed schematic created successfully")


@injected_pytest(_design)
async def test_pyvenv_embed_docker_run(
    schematics_universal,
    a_PersistentDockerEnvFromSchematics,
    logger
):
    """Test pyvenv-embed Docker container with Python execution"""
    logger.info("Testing pyvenv-embed Docker container")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])
    schematic = await schematics_universal(target=project, python_version="3.11")
    
    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="local",
        container_name="test_embed_pyvenv",
    )
    
    # Start container
    await docker_env.start()
    
    try:
        # Run Python script to verify pyenv dependencies
        result = await docker_env.run_script("""
echo "=== Testing pyvenv-embed project ==="
python --version
which python
echo "--- Testing Python imports from requirements.txt ---"
python -c "
import sys
print(f'Python path: {sys.executable}')
print('Testing embedded dependencies:')
deps = [
    ('requests', '2.31.0'),
    ('pandas', '2.1.4'),
    ('numpy', '1.26.2'),
    ('flask', '3.0.0'),
    ('pytest', '7.4.3')
]
for pkg, expected_ver in deps:
    try:
        mod = __import__(pkg)
        version = getattr(mod, '__version__', 'unknown')
        print(f'✓ {pkg} {version} (expected {expected_ver})')
    except ImportError as e:
        print(f'✗ {pkg} import failed: {e}')
"
echo "--- Running app.py ---"
cd /sources/test_requirements
python app.py || echo "app.py execution failed"
        """)
        
        logger.info(f"Test result:\n{result}")
        
        # Verify the test ran successfully
        assert result is not None
        assert "✓ requests" in result
        assert "✓ pandas" in result
        assert "✓ numpy" in result
        assert "✓ flask" in result
        assert "✓ pytest" in result
        
    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 3: Auto-embed with requirements.txt
@injected_pytest(_design)
async def test_auto_embed_requirements_schematic(schematics_universal, logger):
    """Test auto-embed schematic generation with requirements.txt"""
    logger.info("Testing auto-embed schematic generation with requirements.txt")
    
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    assert schematic is not None
    assert schematic.builder is not None
    
    logger.info("✅ Auto-embed requirements.txt schematic created successfully")


@injected_pytest(_design)
async def test_auto_embed_requirements_docker_run(
    schematics_universal,
    a_PersistentDockerEnvFromSchematics,
    logger
):
    """Test auto-embed Docker container with requirements.txt"""
    logger.info("Testing auto-embed Docker container with requirements.txt")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="local",
        container_name="test_embed_req_auto",
    )
    
    # Start container
    await docker_env.start()
    
    try:
        # Run Python script to verify auto-detected requirements.txt
        result = await docker_env.run_script("""
echo "=== Testing auto-embed requirements.txt project ==="
python --version
pip --version
echo "--- Listing installed packages ---"
pip list | grep -E "(requests|pandas|numpy|flask|pytest)" || echo "Expected packages not found"
echo "--- Testing imports ---"
python -c "
import requests, pandas, numpy, flask, pytest
print('✓ All imports successful')
print(f'requests: {requests.__version__}')
print(f'pandas: {pandas.__version__}')
print(f'numpy: {numpy.__version__}')
print(f'flask: {flask.__version__}')
print(f'pytest: {pytest.__version__}')
"
        """)
        
        logger.info(f"Test result:\n{result}")
        
        # Verify the test ran successfully
        assert result is not None
        assert "✓ All imports successful" in result
        assert "requests:" in result
        assert "pandas:" in result
        assert "numpy:" in result
        
    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 4: Pyvenv-embed with setup.py
@injected_pytest(_design)
async def test_pyvenv_embed_setuppy_schematic(schematics_universal, logger):
    """Test pyvenv-embed schematic generation with setup.py"""
    logger.info("Testing pyvenv-embed schematic generation with setup.py")
    
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="pyvenv-embed")])
    schematic = await schematics_universal(target=project, python_version="3.11")
    
    assert schematic is not None
    assert schematic.builder is not None
    
    logger.info("✅ Pyvenv-embed setup.py schematic created successfully")


@injected_pytest(_design)
async def test_pyvenv_embed_setuppy_docker_run(
    schematics_universal,
    a_PersistentDockerEnvFromSchematics,
    logger
):
    """Test pyvenv-embed Docker container with setup.py"""
    logger.info("Testing pyvenv-embed Docker container with setup.py")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="pyvenv-embed")])
    schematic = await schematics_universal(target=project, python_version="3.11")
    
    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="local",
        container_name="test_embed_setuppy",
    )
    
    # Start container
    await docker_env.start()
    
    try:
        # Run Python script to verify setup.py installation
        result = await docker_env.run_script("""
echo "=== Testing pyvenv-embed with setup.py ==="
python --version
echo "--- Checking if package is installed ---"
pip list | grep test-setuppy || echo "test-setuppy package not found"
echo "--- Testing package import ---"
python -c "
try:
    import test_setuppy
    print('✓ test_setuppy package imported successfully')
    # Test that the package is properly installed
    import pkg_resources
    try:
        version = pkg_resources.get_distribution('test-setuppy').version
        print(f'✓ Package version: {version}')
    except:
        print('✗ Could not get package version')
except ImportError as e:
    print(f'✗ test_setuppy import failed: {e}')
"
        """)
        
        logger.info(f"Test result:\n{result}")
        
        # Verify the test ran successfully
        assert result is not None
        assert "✓ test_setuppy package imported successfully" in result
        
    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test cleanup function
@injected_pytest(_design)
async def test_cleanup_containers(a_system, logger):
    """Clean up test containers"""
    logger.info("Cleaning up test containers")
    
    await a_system(
        "docker rm -f test_embed_uv test_embed_pyvenv test_embed_req_auto test_embed_setuppy 2>/dev/null || true"
    )
    
    logger.info("✅ Test containers cleaned up")