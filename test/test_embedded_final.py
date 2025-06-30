"""Test embedded components using @injected_pytest"""

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
    }
)

# Test design - use zeus for Docker host and context
_design = load_env_design + design(
    storage_resolver=_storage_resolver,
    logger=logger,
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",  # Use zeus build context
    ml_nexus_default_base_image="python:3.11-slim",
)


# Test 1: UV auto-embed schematic generation
@injected_pytest(_design)
async def test_uv_auto_embed_schematic(schematics_universal, logger):
    """Test UV auto-embed schematic generation"""
    logger.info("Testing UV auto-embed schematic generation")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    assert schematic is not None
    assert schematic.builder is not None
    assert schematic.builder.base_image is not None
    
    logger.info(f"✅ UV auto-embed schematic created with base image: {schematic.builder.base_image}")


# Test 2: UV auto-embed Docker environment and execution
@injected_pytest(_design)
async def test_uv_auto_embed_docker_run(
    schematics_universal,
    new_DockerEnvFromSchematics,
    logger
):
    """Test UV auto-embed Docker environment creation and Python execution"""
    logger.info("Testing UV auto-embed Docker environment")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
    schematic = await schematics_universal(target=project)
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, 
        schematics=schematic, 
        docker_host="zeus"
    )
    
    # Run test script
    result = await docker_env.run_script("""
echo "=== UV Auto-Embed Test ==="
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'✓ requests {requests.__version__}')"
python -c "import pydantic; print(f'✓ pydantic {pydantic.__version__}')"
echo "Running main.py:"
cd /sources/test_uv && python main.py
    """)
    
    logger.info(f"Test result:\n{result}")
    
    # Verify the test ran successfully
    assert result is not None
    assert "✓ requests" in result
    assert "✓ pydantic" in result
    assert "python" in result.lower()
    
    logger.info("✅ UV auto-embed Docker test passed")


# Test 3: Pyvenv-embed schematic generation
@injected_pytest(_design)
async def test_pyvenv_embed_schematic(schematics_universal, logger):
    """Test pyvenv-embed schematic generation"""
    logger.info("Testing pyvenv-embed schematic generation")
    
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])
    schematic = await schematics_universal(
        target=project, 
        python_version="3.11"
    )
    
    assert schematic is not None
    assert schematic.builder is not None
    assert schematic.builder.base_image is not None
    
    logger.info(f"✅ Pyvenv-embed schematic created with base image: {schematic.builder.base_image}")


# Test 4: Pyvenv-embed Docker environment and execution
@injected_pytest(_design)
async def test_pyvenv_embed_docker_run(
    schematics_universal,
    new_DockerEnvFromSchematics,
    logger
):
    """Test pyvenv-embed Docker environment creation and Python execution"""
    logger.info("Testing pyvenv-embed Docker environment")
    
    # Create project and schematic
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])
    schematic = await schematics_universal(
        target=project, 
        python_version="3.11"
    )
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, 
        schematics=schematic, 
        docker_host="zeus"
    )
    
    # Run test script
    result = await docker_env.run_script("""
echo "=== Pyvenv-Embed Test ==="
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'✓ requests {requests.__version__}')"
python -c "import pandas; print(f'✓ pandas {pandas.__version__}')"
python -c "import numpy; print(f'✓ numpy {numpy.__version__}')"
python -c "import flask; print(f'✓ flask {flask.__version__}')"
    """)
    
    logger.info(f"Test result:\n{result}")
    
    # Verify the test ran successfully
    assert result is not None
    assert "✓ requests" in result
    assert "✓ pandas" in result
    assert "✓ numpy" in result
    assert "✓ flask" in result
    assert "python" in result.lower()
    
    logger.info("✅ Pyvenv-embed Docker test passed")