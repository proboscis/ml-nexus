"""Simple demo to verify zeus Docker context is working with DockerEnvFromSchematics"""

from pathlib import Path
from pinjected import IProxy, design, injected
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from loguru import logger

# Test project root
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Storage resolver
test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
    }
)

# Configure with zeus context
__meta_design__ = design(
    overrides=load_env_design
    + design(
        storage_resolver=test_storage_resolver,
        logger=logger,
        ml_nexus_docker_build_context="zeus",
        docker_host="zeus",
        ml_nexus_default_docker_host_placement=DockerHostPlacement(
            cache_root=Path("/tmp/ml-nexus-zeus-demo/cache"),
            resource_root=Path("/tmp/ml-nexus-zeus-demo/resources"),
            source_root=Path("/tmp/ml-nexus-zeus-demo/source"),
            direct_root=Path("/tmp/ml-nexus-zeus-demo/direct"),
        ),
    )
)


@injected
async def a_demo_zeus_schematics(
    schematics_universal,
    new_DockerEnvFromSchematics,
    ml_nexus_docker_build_context,
    logger,
    /,
):
    """Demo running DockerEnvFromSchematics with zeus context"""
    logger.info(f"Starting demo with Docker context: {ml_nexus_docker_build_context}")

    # Create simple project
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])

    # Generate schematic
    logger.info("Generating schematics...")
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Create Docker environment
    logger.info("Creating DockerEnvFromSchematics...")
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Run simple test
    logger.info("Running test script...")
    result = await docker_env.run_script(
        """
    echo "Running on Zeus with context: $HOSTNAME"
    python --version
    echo "Docker build context was: {context}"
    """.format(context=ml_nexus_docker_build_context)
    )

    logger.info(f"Result:\n{result}")
    logger.info("✅ Demo completed successfully!")

    return result


# IProxy for running with pinjected
demo_zeus: IProxy = a_demo_zeus_schematics()
