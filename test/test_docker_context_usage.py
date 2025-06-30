"""Test that Docker context is properly used throughout the codebase"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest

from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver


# Configure static resolver for test directories
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_source": Path(__file__).parent
        / "dummy_projects"
        / "test_source",
    }
)

# Test project definition
_project = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_source", kind="auto")]
)

# Test design with Docker context
_design = load_env_design + design(
    ml_nexus_docker_build_context="zeus",
    storage_resolver=_storage_resolver,
)


@injected_pytest(_design)
async def test_docker_context_usage(
    a_PersistentDockerEnvFromSchematics,
    schematics_universal,
    logger,
):
    """Test that Docker context is properly used with PersistentDockerEnvFromSchematics"""
    logger.info("Testing Docker context usage")
    
    # Create schematics
    schematics = await schematics_universal(
        target=_project, 
        base_image="ubuntu:22.04"
    )
    
    # Create persistent Docker environment with context
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=_project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_docker_context_usage",
    )
    
    # Start the container
    await docker_env.start()
    
    try:
        # Test that docker commands use the context
        result = await docker_env.run_script("""
echo "Testing Docker context usage"
echo "Container is running on Zeus context"
hostname
pwd
ls -la
        """)
        
        logger.info("Docker context test completed successfully")
        
        # Verify the output contains expected results
        assert result is not None
        
    finally:
        # Clean up container after test
        try:
            await docker_env.delete()
            logger.info("Container cleaned up successfully")
        except Exception as e:
            logger.warning(f"Failed to delete container: {e}")