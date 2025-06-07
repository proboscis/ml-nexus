"""Simple test to build embedded Docker image and check basic Python"""

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
            "test/dummy_projects/test_requirements": Path(__file__).parent
            / "dummy_projects"
            / "test_requirements",
            "test/dummy_projects/test_uv": Path(__file__).parent
            / "dummy_projects"
            / "test_uv",
        }
    )


# Test for pyvenv-embed project
test_pyvenv_embed_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_requirements", kind="pyvenv-embed")]
)

test_schematics_pyvenv_embed: IProxy = schematics_universal(
    target=test_pyvenv_embed_project, python_version="3.11"
)

# Use non-persistent DockerEnvFromSchematics for quicker testing
test_docker_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_pyvenv_embed_project,
    schematics=test_schematics_pyvenv_embed,
    docker_host="zeus",
)

# Simple test - just check Python version
test_simple_python: IProxy = test_docker_env.run_script(
    """
echo "Testing Python in embedded container"
python --version
echo "Python test complete"
"""
)

__design__ = load_env_design + design(
    ml_nexus_docker_build_context=ml_nexus_docker_build_context,
    storage_resolver=storage_resolver,
)
