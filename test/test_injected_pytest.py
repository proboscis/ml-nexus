from pathlib import Path

from pinjected import design
from pinjected.test import injected_pytest

from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus.project_structure import ProjectDef, ProjectDir

# Setup test paths
_dir = Path(__file__).parent / "dummy_projects"

# Create storage resolver directly
_storage_resolver = StaticStorageResolver({
    "test/dummy_projects/test_requirements": _dir / "test_requirements",
    "test/dummy_projects/test_setuppy": _dir / "test_setuppy",
})

# Define test project directly  
_project = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")]
)

# Create test design with all dependencies
_design = design(
    storage_resolver=_storage_resolver,
    ml_nexus_docker_build_context="zeus",
)

@injected_pytest(_design)
def test_something(logger):
    logger.info("Test something is running")
    assert True

@injected_pytest(_design)
async def test_requirements_run(
    a_PersistentDockerEnvFromSchematics,
    schematics_universal,
    logger
):
    logger.info("Starting test_requirements_run")
    
    # Create schematics
    schematics = await schematics_universal(
        target=_project,
        python_version="3.11"
    )
    
    # Create and start docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=_project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_requirements",
    )
    
    await docker_env.start()
    
    try:
        # Run the test script
        await docker_env.run_script("""
echo "=== Testing uv-pip-embed with requirements.txt ==="
echo ""
echo "1. Python version:"
python --version
echo ""
echo "2. UV version:"
uv --version
echo ""
echo "3. Which python:"
which python
echo ""
echo "4. Installed packages:"
pip list | grep -E "(requests|numpy)"
echo ""
echo "5. Test imports:"
python -c "
import requests
import numpy as np
print(f'✅ requests {requests.__version__}')
print(f'✅ numpy {np.__version__}')
print('✅ All imports successful!')
"        """)
        
        logger.info("Test completed successfully")
    finally:
        # Clean up after test
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")