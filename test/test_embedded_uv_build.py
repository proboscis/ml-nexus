"""Test UV embedded Docker image with Python execution"""

from pathlib import Path
from pinjected import design, instance, injected, IProxy

from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
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
            "test/dummy_projects/test_uv": Path(__file__).parent
            / "dummy_projects"
            / "test_uv",
        }
    )


# Test for UV auto-embed project
test_uv_embed_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_uv", kind="auto-embed")]
)

test_schematics_uv_embed: IProxy = schematics_universal(target=test_uv_embed_project)

# Use non-persistent DockerEnvFromSchematics for quicker testing
test_docker_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_uv_embed_project,
    schematics=test_schematics_uv_embed,
    docker_host="zeus",
)

# Test Python execution in UV container
test_uv_python: IProxy = test_docker_env.run_script(
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

__design__ = load_env_design + design(
    ml_nexus_docker_build_context=ml_nexus_docker_build_context,
    storage_resolver=storage_resolver,
)
