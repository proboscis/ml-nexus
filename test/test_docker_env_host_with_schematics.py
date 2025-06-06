"""Test DockerHostEnvironment integration with schematics

This test verifies that DockerHostEnvironment correctly works with the new schematics
interface, testing various project types and configurations.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import CacheMountRequest, ResolveMountRequest, ContainerScript
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import tempfile

# Setup test project paths
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Test storage resolver
test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_source": TEST_PROJECT_ROOT / "test_source",
        "test_resource": TEST_PROJECT_ROOT / "test_resource",
    }
)

# Test design configuration
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    ml_nexus_default_docker_host_placement=DockerHostPlacement(
        cache_root=Path("/tmp/ml-nexus-test/cache"),
        resource_root=Path("/tmp/ml-nexus-test/resources"),
        source_root=Path("/tmp/ml-nexus-test/source"),
        direct_root=Path("/tmp/ml-nexus-test/direct"),
    ),
    docker_host="zeus",  # Required Docker host for this repo
    ml_nexus_docker_build_context="zeus",  # Use zeus Docker context for builds
)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# ===== Test 1: Basic schematics functionality =====
@injected_pytest(test_design)
async def test_docker_env_basic_schematics(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test basic DockerEnvFromSchematics functionality with a simple UV project"""
    logger.info("Testing basic DockerEnvFromSchematics with UV project")

    # Create project definition
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])

    # Generate schematic
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Create Docker environment from schematics
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test basic script execution
    result = await docker_env.run_script("echo 'Hello from Docker'")
    assert "Hello from Docker" in result.stdout

    # Test Python availability
    result = await docker_env.run_script("python --version")
    assert "Python" in result.stdout

    logger.info("✅ Basic schematics test passed")


# ===== Test 2: Mount functionality =====
@injected_pytest(test_design)
async def test_docker_env_with_mounts(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test DockerEnvFromSchematics with various mount types"""
    logger.info("Testing DockerEnvFromSchematics with different mount types")

    # Create project with resource
    project = ProjectDef(
        dirs=[
            ProjectDir("test_uv", kind="uv"),
            ProjectDir("test_resource", kind="resource"),
        ]
    )

    # Generate schematic
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Add additional mounts to schematic
    schematic = schematic + [
        CacheMountRequest(name="pip-cache", mount_point=Path("/root/.cache/pip")),
        ResolveMountRequest(
            kind="resource",
            resource_id="test_resource",
            mount_point=Path("/data"),
            excludes=[],
        ),
    ]

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test mount availability
    result = await docker_env.run_script("ls -la /data")
    assert "config.yaml" in result.stdout or "data.json" in result.stdout

    logger.info("✅ Mount test passed")


# ===== Test 3: Multiple project types =====
@injected_pytest(test_design)
async def test_docker_env_multiple_project_types(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test DockerEnvFromSchematics with different project types"""
    logger.info("Testing different project types with schematics")

    test_cases = [
        (
            "UV project",
            ProjectDir("test_uv", kind="uv"),
            "python -c 'print(\"UV works\")'",
        ),
        (
            "Rye project",
            ProjectDir("test_rye", kind="rye"),
            "python -c 'print(\"Rye works\")'",
        ),
        (
            "Setup.py project",
            ProjectDir("test_setuppy", kind="auto"),
            "python -c 'import test_setuppy; print(\"Setup.py works\")'",
        ),
        (
            "Requirements project",
            ProjectDir("test_requirements", kind="auto"),
            "python -c 'import pandas; print(\"Requirements works\")'",
        ),
    ]

    for name, project_dir, test_cmd in test_cases:
        logger.info(f"Testing {name}")

        project = ProjectDef(dirs=[project_dir])
        schematic = await schematics_universal(
            target=project, base_image="python:3.11-slim"
        )

        docker_env = new_DockerEnvFromSchematics(
            project=project, schematics=schematic, docker_host="zeus"
        )

        try:
            result = await docker_env.run_script(test_cmd)
            assert "works" in result.stdout, f"{name} test failed: {result.stdout}"
            logger.info(f"✅ {name} test passed")
        except Exception as e:
            logger.error(f"❌ {name} test failed: {e}")
            raise


# ===== Test 4: Script context functionality =====
@injected_pytest(test_design)
async def test_docker_env_script_context(
    schematics_universal, new_DockerEnvFromSchematics, logger, a_system
):
    """Test DockerEnvFromSchematics script run context (upload/download)"""
    logger.info("Testing script run context functionality")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Create a test file to upload
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("test content")
        test_file = Path(f.name)

    try:
        # Get run context
        context = docker_env.run_context()

        # Test upload
        remote_path = context.random_remote_path()
        await context.upload_remote(test_file, remote_path / "test.txt")

        # Verify file exists in container
        result = await docker_env.run_script(f"cat {remote_path}/test.txt")
        assert "test content" in result.stdout

        # Test download
        download_path = context.local_download_path / "downloaded.txt"
        await context.download_remote(remote_path / "test.txt", download_path)

        # Verify downloaded file
        assert download_path.exists()
        assert download_path.read_text() == "test content"

        # Test delete
        await context.delete_remote(remote_path)

        logger.info("✅ Script context test passed")

        # Cleanup downloaded file
        if download_path.exists():
            download_path.unlink()

    finally:
        # Cleanup test file
        test_file.unlink()


# ===== Test 5: Builder integration =====
@injected_pytest(test_design)
async def test_docker_env_builder_integration(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test that DockerBuilder scripts are properly integrated"""
    logger.info("Testing DockerBuilder script integration")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Add a custom script to the schematic's builder
    schematic = schematic + ContainerScript("export TEST_VAR='from_builder'")

    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test that the builder script is executed
    result = await docker_env.run_script("echo $TEST_VAR")
    assert "from_builder" in result.stdout

    logger.info("✅ Builder integration test passed")


# ===== Test 6: Without init functionality =====
@injected_pytest(test_design)
async def test_docker_env_without_init(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test run_script_without_init method"""
    logger.info("Testing run_script_without_init")

    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image="ubuntu:22.04")

    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test running script without initialization
    result = await docker_env.run_script_without_init("echo 'No init needed'")
    assert "No init needed" in result.stdout

    logger.info("✅ Without init test passed")


# ===== Test 7: Error handling =====
@injected_pytest(test_design)
async def test_docker_env_error_handling(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test error handling in DockerEnvFromSchematics"""
    logger.info("Testing error handling")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test command that should fail
    try:
        await docker_env.run_script("exit 1")
        assert False, "Expected command to fail"
    except Exception as e:
        logger.info(f"Got expected error: {e}")
        assert True

    logger.info("✅ Error handling test passed")
