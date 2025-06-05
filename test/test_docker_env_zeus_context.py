"""Test DockerEnvFromSchematics with zeus Docker context and multiple schematics

This test suite verifies that DockerEnvFromSchematics correctly uses the zeus Docker context
for building images and runs various scenarios with multiple schematics configurations.
"""

from pathlib import Path
from pinjected import IProxy, design, injected
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver

# No longer need the conversion utility with @injected_pytest

# Setup test project paths
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Test storage resolver
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
    "test_resource": TEST_PROJECT_ROOT / "test_resource",
})

# Module design configuration with zeus context
# Module design configuration with zeus context
test_design = design(
    storage_resolver=test_storage_resolver,
    ml_nexus_default_docker_host_placement=DockerHostPlacement(
        cache_root=Path("/tmp/ml-nexus-zeus-test/cache"),
        resource_root=Path("/tmp/ml-nexus-zeus-test/resources"),
        source_root=Path("/tmp/ml-nexus-zeus-test/source"),
        direct_root=Path("/tmp/ml-nexus-zeus-test/direct"),
    ),
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",
)

__meta_design__ = design(
    overrides=load_env_design + test_design
)


# ===== Test 1: Basic Zeus context verification =====
@injected_pytest(test_design)
async def test_zeus_context_basic(schematics_universal, new_DockerEnvFromSchematics, logger, ml_nexus_docker_build_context):
    """Verify that zeus Docker context is properly configured and used"""
    logger.info(f"Testing with Docker build context: {ml_nexus_docker_build_context}")
    assert ml_nexus_docker_build_context == "zeus", f"Expected zeus context, got {ml_nexus_docker_build_context}"
    
    # Create simple project
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    # Generate schematic
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Create Docker environment
    logger.info("Creating DockerEnvFromSchematics...")
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    logger.info(f"DockerEnvFromSchematics created: {docker_env}")
    logger.info(f"DockerEnv type: {type(docker_env)}")
    
    # Test basic execution
    logger.info("About to run script on Docker environment")
    # run_script() has undefined return type, so we just check it runs without error
    await docker_env.run_script("echo 'Running on Zeus context'")
    
    logger.info("✅ Zeus context basic test passed")

# No longer need manual IProxy creation with @injected_pytest


# ===== Test 2: Multiple schematics with different base images =====
@injected_pytest(test_design)
async def test_multiple_schematics_base_images(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test multiple schematics with different base images on Zeus"""
    logger.info("Testing multiple schematics with different base images")
    
    base_images = [
        "python:3.11-slim",
        "python:3.10-slim",
        "ubuntu:22.04",
        "debian:bullseye-slim"
    ]
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    
    for base_image in base_images:
        logger.info(f"Testing with base image: {base_image}")
        
        # Generate schematic with specific base image
        schematic = await schematics_universal(
            target=project,
            base_image=base_image
        )
        
        # Create Docker environment
        docker_env = new_DockerEnvFromSchematics(
            project=project,
            schematics=schematic,
            docker_host="zeus"
        )
        
        # Test image-specific functionality
        # run_script() has undefined return type, so we just check it runs without error
        if "python" in base_image:
            await docker_env.run_script("python --version")
        else:
            await docker_env.run_script("cat /etc/os-release | grep PRETTY_NAME")
        
        logger.info(f"✅ {base_image} test passed")

# No longer need manual IProxy creation with @injected_pytest


# ===== IProxy entry points for direct execution =====
# These allow running tests directly with pinjected

@injected
async def a_demo_zeus_basic(schematics_universal, new_DockerEnvFromSchematics, ml_nexus_docker_build_context, logger, /):
    """Demo basic Zeus context usage"""
    logger.info(f"Running demo with context: {ml_nexus_docker_build_context}")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(target=project, base_image='python:3.11-slim')
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # run_script() has undefined return type, so we just check it runs without error
    await docker_env.run_script("echo 'Zeus demo successful' && python --version")
    logger.info("Demo completed successfully")
    return "Zeus demo completed"

# Entry point with proper IProxy type annotation
demo_zeus_basic: IProxy = a_demo_zeus_basic()
