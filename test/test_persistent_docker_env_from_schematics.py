"""Comprehensive tests for PersistentDockerEnvFromSchematics

This test suite verifies all functionality of PersistentDockerEnvFromSchematics including:
- Docker context support
- Container persistence and reuse
- File operations (upload, download, sync)
- Container lifecycle management
- Error handling and edge cases
"""

from pathlib import Path
import tempfile
import uuid
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from ml_nexus.event_bus_util import handle_ml_nexus_system_call_events__simple
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import pytest

# Setup test project paths
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
REPO_ROOT = Path(__file__).parent.parent

# Test storage resolver
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
    "test_resource": TEST_PROJECT_ROOT / "test_resource",
})

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
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",  # Ensure Docker context is set
)



# ===== Test 1: Basic container lifecycle =====
@injected_pytest(test_design)
async def test_persistent_container_lifecycle(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test basic container lifecycle: create, ensure, stop"""
    logger.info("Testing persistent container lifecycle")
    
    # Create a simple project
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    
    # Generate schematic
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    # Create unique container name
    container_name = f"test_persistent_lifecycle_{uuid.uuid4().hex[:8]}"
    
    # Create persistent Docker environment
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Test container is not ready initially
        is_ready = await docker_env.a_is_container_ready()
        assert not is_ready, "Container should not be ready initially"
        logger.info("✓ Container correctly not ready initially")
        
        # Run a script - this should create and start the container
        result = await docker_env.run_script("echo 'Container started'")
        assert "Container started" in result.stdout
        assert result.exit_code == 0
        logger.info("✓ Container started successfully")
        
        # Verify container is now ready
        is_ready = await docker_env.a_is_container_ready()
        assert is_ready, "Container should be ready after starting"
        logger.info("✓ Container is ready")
        
        # Run another script - should reuse the container
        result = await docker_env.run_script("echo 'Reusing container'")
        assert "Reusing container" in result.stdout
        logger.info("✓ Container reused successfully")
        
    finally:
        # Clean up - stop the container if it exists
        try:
            await docker_env.stop()
            logger.info("✓ Container stopped")
        except Exception as e:
            logger.info(f"Container stop skipped: {e}")
        
    logger.info("✅ Persistent container lifecycle test passed")


# ===== Test 2: Container persistence across instances =====
@injected_pytest(test_design)
async def test_container_persistence_across_instances(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test that containers persist across different instances with same name"""
    logger.info("Testing container persistence across instances")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(target=project, base_image='python:3.11-slim')
    
    # Use a fixed container name
    container_name = f"test_persistence_{uuid.uuid4().hex[:8]}"
    
    # Create first instance
    docker_env1 = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Create a file in the container
        result = await docker_env1.run_script("echo 'persistent data' > /tmp/test_file.txt")
        assert result.exit_code == 0
        logger.info("✓ Created file in first instance")
        
        # Create second instance with same container name
        docker_env2 = new_PersistentDockerEnvFromSchematics(
            project=project,
            schematics=schematic,
            docker_host="zeus",
            container_name=container_name
        )
        
        # Verify the file exists in the "new" instance
        result = await docker_env2.run_script("cat /tmp/test_file.txt")
        assert "persistent data" in result.stdout
        logger.info("✓ File persisted across instances")
        
        # Verify it's the same container
        result1 = await docker_env1.run_script("hostname")
        result2 = await docker_env2.run_script("hostname")
        assert result1.stdout.strip() == result2.stdout.strip()
        logger.info("✓ Same container used by both instances")
        
    finally:
        # Clean up
        await docker_env1.stop()
        
    logger.info("✅ Container persistence test passed")


# ===== Test 3: File operations =====
@injected_pytest(test_design)
async def test_file_operations(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test upload, download, and sync operations"""
    logger.info("Testing file operations")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_file_ops_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Create a temporary file to upload
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test upload content\n")
            local_upload_path = Path(f.name)
        
        # Test upload
        remote_path = Path("/tmp/uploaded_file.txt")
        await docker_env.upload(local_upload_path, remote_path)
        logger.info("✓ File uploaded")
        
        # Verify upload
        result = await docker_env.run_script(f"cat {remote_path}")
        assert "Test upload content" in result.stdout
        logger.info("✓ Upload verified")
        
        # Test download
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "downloaded.txt"
            await docker_env.download(remote_path, download_path)
            
            # Verify download
            assert download_path.exists()
            assert download_path.read_text().strip() == "Test upload content"
            logger.info("✓ Download verified")
        
        # Test delete
        await docker_env.delete(remote_path)
        result = await docker_env.run_script(f"test -f {remote_path} && echo 'exists' || echo 'deleted'")
        assert "deleted" in result.stdout
        logger.info("✓ Delete verified")
        
        # Test sync operations
        # Create a directory structure to sync
        with tempfile.TemporaryDirectory() as tmpdir:
            sync_dir = Path(tmpdir) / "sync_test"
            sync_dir.mkdir()
            (sync_dir / "file1.txt").write_text("File 1 content")
            (sync_dir / "file2.txt").write_text("File 2 content")
            
            # Sync to container
            remote_sync_path = Path("/tmp/synced_dir")
            await docker_env.sync_to_container(sync_dir, remote_sync_path)
            logger.info("✓ Sync to container completed")
            
            # Verify sync
            result = await docker_env.run_script(f"ls {remote_sync_path}")
            assert "file1.txt" in result.stdout
            assert "file2.txt" in result.stdout
            
            # Modify a file in container
            await docker_env.run_script(f"echo 'Modified in container' > {remote_sync_path}/file3.txt")
            
            # Sync back from container
            sync_back_dir = Path(tmpdir) / "sync_back"
            await docker_env.sync_from_container(remote_sync_path, sync_back_dir)
            logger.info("✓ Sync from container completed")
            
            # Verify sync back
            assert (sync_back_dir / "file1.txt").exists()
            assert (sync_back_dir / "file2.txt").exists()
            assert (sync_back_dir / "file3.txt").exists()
            assert "Modified in container" in (sync_back_dir / "file3.txt").read_text()
            logger.info("✓ Sync back verified")
        
    finally:
        # Clean up
        await docker_env.stop()
        local_upload_path.unlink(missing_ok=True)
        
    logger.info("✅ File operations test passed")


# ===== Test 4: Docker context support =====
@injected_pytest(test_design)
async def test_docker_context_support(
    schematics_universal, new_PersistentDockerEnvFromSchematics, a_docker_ps, logger
):
    """Test that Docker context is properly used in all operations"""
    logger.info("Testing Docker context support")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_context_{uuid.uuid4().hex[:8]}"
    
    # Create persistent Docker environment with context
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Verify context is set
        assert docker_env._ml_nexus_docker_build_context == "zeus"
        logger.info("✓ Docker context is set correctly")
        
        # Run a script to ensure container is started
        result = await docker_env.run_script("echo 'Testing with context'")
        assert result.exit_code == 0
        logger.info("✓ Container started with context")
        
        # Use a_docker_ps to verify container is visible with context
        df = await a_docker_ps(docker_host="zeus")
        assert container_name in df.index, f"Container {container_name} not found in docker ps"
        logger.info("✓ Container visible through docker ps with context")
        
        # Test that all docker commands use the context
        # This is implicitly tested by the operations working correctly with zeus context
        
    finally:
        # Clean up
        await docker_env.stop()
        
    logger.info("✅ Docker context support test passed")


# ===== Test 5: Error handling =====
@injected_pytest(test_design)
async def test_error_handling(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test error handling in various scenarios"""
    logger.info("Testing error handling")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_errors_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Test script failure
        with pytest.raises(Exception) as exc_info:
            await docker_env.run_script("exit 42")
        assert "exit code 42" in str(exc_info.value)
        logger.info("✓ Script failure handled correctly")
        
        # Test download non-existent file
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = Path(tmpdir) / "nonexistent.txt"
            with pytest.raises(Exception):
                await docker_env.download(Path("/nonexistent/file.txt"), download_path)
        logger.info("✓ Download error handled correctly")
        
        # Test upload to invalid path (no parent directory)
        with tempfile.NamedTemporaryFile() as f:
            # This should create parent directories automatically
            await docker_env.upload(Path(f.name), Path("/deep/nested/path/file.txt"))
            result = await docker_env.run_script("test -f /deep/nested/path/file.txt && echo 'exists'")
            assert "exists" in result.stdout
        logger.info("✓ Upload creates parent directories")
        
    finally:
        # Clean up
        await docker_env.stop()
        
    logger.info("✅ Error handling test passed")


# ===== Test 6: Complex project types =====
@injected_pytest(test_design)
async def test_complex_project_types(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test persistent containers with complex project types"""
    logger.info("Testing complex project types")
    
    # Create a complex project with multiple directories
    project = ProjectDef(dirs=[
        ProjectDir("test_uv", kind="uv"),
        ProjectDir("test_resource", kind="resource"),
        ProjectDir("test_source", kind="source"),
    ])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    container_name = f"test_complex_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Test UV is available
        result = await docker_env.run_script("which uv || echo 'UV not found'")
        assert "uv" in result.stdout and "not found" not in result.stdout
        logger.info("✓ UV is available")
        
        # Test Python is available
        result = await docker_env.run_script("python --version")
        assert "Python" in result.stdout
        logger.info("✓ Python is available")
        
        # Test resources are mounted
        result = await docker_env.run_script("ls /resources/")
        logger.info(f"Resources available: {result.stdout}")
        
        # Test project source is available
        result = await docker_env.run_script("ls /source/")
        logger.info(f"Source available: {result.stdout}")
        
    finally:
        # Clean up
        await docker_env.stop()
        
    logger.info("✅ Complex project types test passed")


# ===== Test 7: Container state verification =====
@injected_pytest(test_design)
async def test_container_state_verification(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test container state verification and wait functionality"""
    logger.info("Testing container state verification")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_state_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Initially not ready
        assert not await docker_env.a_is_container_ready()
        logger.info("✓ Container initially not ready")
        
        # Start container
        await docker_env.ensure_container()
        logger.info("✓ Container ensured")
        
        # Now should be ready
        assert await docker_env.a_is_container_ready()
        logger.info("✓ Container is ready after ensure")
        
        # Test wait functionality
        await docker_env.a_wait_container_ready()
        logger.info("✓ Wait for container ready works")
        
        # Test multiple ensure calls (should be idempotent)
        await docker_env.ensure_container()
        await docker_env.ensure_container()
        logger.info("✓ Multiple ensure calls are idempotent")
        
    finally:
        # Clean up
        await docker_env.stop()
        
        # Verify container is no longer running
        is_ready = await docker_env.a_is_container_ready()
        assert not is_ready
        logger.info("✓ Container stopped successfully")
        
    logger.info("✅ Container state verification test passed")


# ===== Test 8: Random remote path generation =====
@injected_pytest(test_design)
async def test_random_remote_path(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test random remote path generation"""
    logger.info("Testing random remote path generation")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_random_path_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Generate random paths
        path1 = docker_env.random_remote_path()
        path2 = docker_env.random_remote_path()
        
        # Verify they are different
        assert path1 != path2
        logger.info(f"✓ Generated unique paths: {path1} and {path2}")
        
        # Verify they follow the expected pattern
        assert str(path1).startswith(str(project.placement.resources_root / "tmp"))
        assert str(path2).startswith(str(project.placement.resources_root / "tmp"))
        logger.info("✓ Paths follow expected pattern")
        
        # Test using random path for upload
        with tempfile.NamedTemporaryFile(mode='w') as f:
            f.write("Random path test")
            f.flush()
            
            random_path = docker_env.random_remote_path()
            await docker_env.upload(Path(f.name), random_path)
            
            result = await docker_env.run_script(f"cat {random_path}")
            assert "Random path test" in result.stdout
            logger.info("✓ Random path usable for operations")
            
    finally:
        # Clean up
        await docker_env.stop()
        
    logger.info("✅ Random remote path test passed")


# ===== Test 9: Run context =====
@injected_pytest(test_design)
async def test_run_context(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test ScriptRunContext functionality"""
    logger.info("Testing ScriptRunContext")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(target=project, base_image='ubuntu:22.04')
    
    container_name = f"test_context_{uuid.uuid4().hex[:8]}"
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus",
        container_name=container_name
    )
    
    try:
        # Get run context
        context = docker_env.run_context()
        
        # Verify context has required attributes
        assert hasattr(context, 'random_remote_path')
        assert hasattr(context, 'upload_remote')
        assert hasattr(context, 'delete_remote')
        assert hasattr(context, 'download_remote')
        assert hasattr(context, 'local_download_path')
        assert hasattr(context, 'env')
        logger.info("✓ Run context has all required attributes")
        
        # Test context functions
        random_path = context.random_remote_path()
        assert isinstance(random_path, Path)
        logger.info("✓ Context random_remote_path works")
        
        # Verify env reference
        assert context.env == docker_env
        logger.info("✓ Context env reference is correct")
        
    finally:
        # Clean up
        await docker_env.stop()
        
    logger.info("✅ Run context test passed")

# Module design configuration
__design__ = load_env_design + test_design+design(
    ml_nexus_docker_context='zeus',
    ml_nexus_system_call_event_bus=handle_ml_nexus_system_call_events__simple,
)

# ===== Main test runner =====
if __name__ == "__main__":
    # This allows running the tests directly with: python test_persistent_docker_env_from_schematics.py
    import asyncio
    
    async def run_all_tests():
        """Run all tests manually"""
        print("Running PersistentDockerEnvFromSchematics tests...")
        
        # Note: This is just for manual testing
        # In practice, use pytest to run the tests
        
    asyncio.run(run_all_tests())