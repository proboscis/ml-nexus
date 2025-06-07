"""Test to verify Python execution works in embedded pyvenv containers"""

from pathlib import Path
from pinjected import design, instance, injected, IProxy

from ml_nexus import load_env_design
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver


@instance
def ml_nexus_docker_build_context():
    return "zeus"


@instance
def storage_resolver():
    # Configure static resolver for test directories
    return StaticStorageResolver(
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


# Test for pyvenv-embed project
test_pyvenv_embed_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_requirements", kind="pyvenv-embed")]
)

test_schematics_pyvenv_embed: IProxy = schematics_universal(
    target=test_pyvenv_embed_project, python_version="3.11"
)

test_pyvenv_embed_docker: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_pyvenv_embed_project,
    schematics=test_schematics_pyvenv_embed,
    docker_host="zeus",
    container_name="test_pyvenv_embed_python_exec",
)

# Test Python execution
test_pyvenv_embed_python_exec: IProxy = test_pyvenv_embed_docker.run_script(
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

__design__ = load_env_design + design(
    ml_nexus_docker_build_context=ml_nexus_docker_build_context,
    storage_resolver=storage_resolver,
)
