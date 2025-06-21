"""Test that Docker context is properly used throughout the codebase"""

from pathlib import Path
from pinjected import instance, design, injected, IProxy

from ml_nexus import load_env_design
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver


@instance
def ml_nexus_docker_build_context():
    """Set Zeus as the Docker context for testing"""
    return "zeus"


@instance
def storage_resolver():
    """Configure static resolver for test directories"""
    return StaticStorageResolver(
        {
            "test/dummy_projects/test_source": Path(__file__).parent
            / "dummy_projects"
            / "test_source",
        }
    )


# Test project definition
test_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_source", kind="auto")]
)

# Create schematics
test_schematics: IProxy = schematics_universal(
    target=test_project, base_image="ubuntu:22.04"
)

# Create persistent Docker environment with context
test_docker_env: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_project,
    schematics=test_schematics,
    docker_host="zeus",
    container_name="test_docker_context_usage",
)

# Test that docker commands use the context
test_run: IProxy = test_docker_env.run_script("""
echo "Testing Docker context usage"
echo "Container is running on Zeus context"
hostname
pwd
ls -la
""")

# Clean up container after test
test_cleanup: IProxy = test_docker_env.delete()

__design__ = load_env_design + design(
    ml_nexus_docker_build_context=ml_nexus_docker_build_context,
    storage_resolver=storage_resolver,
)
