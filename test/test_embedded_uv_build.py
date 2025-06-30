"""Test UV embedded Docker image with Python execution"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest

from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver

# Configure static resolver for test directories
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_uv": Path(__file__).parent
        / "dummy_projects"
        / "test_uv",
    }
)

# Test design configuration
_design = load_env_design + design(
    ml_nexus_docker_build_context="zeus",
    storage_resolver=_storage_resolver,
)


@injected_pytest(_design)
async def test_uv_embedded_python_execution(
    schematics_universal,
    new_DockerEnvFromSchematics,
    logger,
):
    """Test UV embedded Docker image with Python execution"""
    logger.info("Testing UV embedded Docker image")
    
    # Create UV auto-embed project - use the storage resolver key
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_uv", kind="auto-embed")]
    )
    
    # Generate schematics
    schematics = await schematics_universal(target=project)
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
    )
    
    # Test Python execution in UV container
    result = await docker_env.run_script(
        """
echo "=== Testing Python in UV embedded container ==="
echo "1. Python version:"
python --version

echo -e "\n2. UV version:"
uv --version

echo -e "\n3. Python location:"
which python

echo -e "\n4. Test Python execution:"
python -c "
import sys
print(f'Python: {sys.version}')
print(f'Executable: {sys.executable}')
print('UV embedded container working!')
"

echo -e "\n5. Test main.py from project:"
python main.py

echo -e "\n=== UV Python test complete ==="
"""
    )
    
    logger.info(f"Test result:\n{result.stdout}")
    
    # Verify the test ran successfully
    assert result is not None
    assert "UV embedded container working!" in result.stdout
    assert "python" in result.stdout.lower()
    
    logger.info("✅ UV embedded Python execution test passed")