"""Test to verify Python execution works in embedded pyvenv containers"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Configure static resolver for test directories
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_requirements": Path(__file__).parent
        / "dummy_projects"
        / "test_requirements",
        "test/dummy_projects/test_uv": Path(__file__).parent
        / "dummy_projects"
        / "test_uv",
        "test/dummy_projects/test_setuppy": Path(__file__).parent
        / "dummy_projects"
        / "test_setuppy",
    }
)

# Test design configuration
_design = load_env_design + design(
    ml_nexus_docker_build_context="zeus",
    storage_resolver=_storage_resolver,
    logger=logger
)


# Test: Python execution in pyvenv-embed container
@injected_pytest(_design)
async def test_pyvenv_embed_python_execution(
    schematics_universal,
    a_PersistentDockerEnvFromSchematics,
    logger
):
    """Test Python execution in pyvenv-embed container"""
    logger.info("Testing Python execution in pyvenv-embed container")
    
    # Create project
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_requirements", kind="pyvenv-embed")]
    )
    
    # Generate schematics
    schematics = await schematics_universal(
        target=project, 
        python_version="3.11"
    )
    
    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_pyvenv_embed_python_exec",
    )
    
    # Start container
    await docker_env.start()
    
    try:
        # Run comprehensive Python test script
        result = await docker_env.run_script(
            """
echo "=== Testing Python execution in pyvenv-embed container ==="
echo "1. Checking Python version:"
python --version

echo -e "\n2. Checking which Python:"
which python

echo -e "\n3. Checking pip list:"
pip list

echo -e "\n4. Testing Python import and execution:"
python -c "
import sys
print(f'Python executable: {sys.executable}')
print(f'Python version: {sys.version}')
print(f'Python path: {sys.path[:3]}...')

# Test that we can import and use modules
import json
import os
print(f'Current directory: {os.getcwd()}')
print('JSON module works:', json.dumps({'test': 'success'}))

# Test that we can run simple computations
result = sum(range(10))
print(f'Sum of range(10): {result}')
"

echo -e "\n5. Testing Python script execution from file:"
cat > test_script.py << 'EOF'
#!/usr/bin/env python
import sys
print(f"Running from script file")
print(f"Arguments: {sys.argv}")
print("Script execution successful!")
EOF

python test_script.py arg1 arg2

echo -e "\n=== All Python tests completed ==="
"""
        )
        
        logger.info(f"Test result:\n{result}")
        
        # Verify the test ran successfully
        assert result is not None
        assert "Python executable:" in result
        assert "Python version:" in result
        assert "JSON module works:" in result
        assert "Sum of range(10): 45" in result
        assert "Script execution successful!" in result
        assert "Arguments: ['test_script.py', 'arg1', 'arg2']" in result
        
    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")