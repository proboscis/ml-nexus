"""Test DockerEnvFromSchematics with zeus Docker context and multiple schematics

This test suite verifies that DockerEnvFromSchematics correctly uses the zeus Docker context
for building images and runs various scenarios with multiple schematics configurations.
"""

from pathlib import Path
from pinjected import IProxy, design, injected
from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import CacheMountRequest, ResolveMountRequest, ContainerScript
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus.schematics_util.universal import EnvComponent
from loguru import logger
import tempfile

# Import the conversion utility
from test.iproxy_test_utils import to_pytest

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
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger,
        ml_nexus_default_docker_host_placement=DockerHostPlacement(
            cache_root=Path("/tmp/ml-nexus-zeus-test/cache"),
            resource_root=Path("/tmp/ml-nexus-zeus-test/resources"),
            source_root=Path("/tmp/ml-nexus-zeus-test/source"),
            direct_root=Path("/tmp/ml-nexus-zeus-test/direct"),
        ),
        docker_host="zeus",  # Using zeus as the remote Docker host
        ml_nexus_docker_build_context="zeus",  # Using zeus Docker context for builds
    )
)


# ===== Test 1: Basic Zeus context verification =====
@injected
async def a_test_zeus_context_basic(schematics_universal, new_DockerEnvFromSchematics, logger, ml_nexus_docker_build_context):
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
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test basic execution
    result = await docker_env.run_script("echo 'Running on Zeus context'")
    assert "Running on Zeus context" in result
    
    logger.info("✅ Zeus context basic test passed")

# Create IProxy and convert to pytest
test_zeus_context_basic_iproxy: IProxy = a_test_zeus_context_basic(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger"),
    injected("ml_nexus_docker_build_context")
)
test_zeus_context_basic = to_pytest(test_zeus_context_basic_iproxy)


# ===== Test 2: Multiple schematics with different base images =====
@injected
async def a_test_multiple_schematics_base_images(schematics_universal, new_DockerEnvFromSchematics, logger):
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
        if "python" in base_image:
            result = await docker_env.run_script("python --version")
            assert "Python" in result
        else:
            result = await docker_env.run_script("cat /etc/os-release | grep PRETTY_NAME")
            assert "NAME" in result
        
        logger.info(f"✅ {base_image} test passed")

# Create IProxy and convert to pytest
test_multiple_schematics_base_images_iproxy: IProxy = a_test_multiple_schematics_base_images(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_multiple_schematics_base_images = to_pytest(test_multiple_schematics_base_images_iproxy)


# ===== Test 3: Complex multi-project schematics =====
@injected
async def a_test_complex_multi_project_schematics(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test complex schematics with multiple project types and dependencies"""
    logger.info("Testing complex multi-project schematics on Zeus")
    
    # Create complex project with multiple directories
    project = ProjectDef(dirs=[
        ProjectDir("test_uv", kind="uv"),
        ProjectDir("test_source", kind="source"),
        ProjectDir("test_resource", kind="resource"),
    ])
    
    # Generate schematic
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Add multiple mount requests
    additional_mounts = [
        CacheMountRequest(name="pip-cache", mount_point=Path("/root/.cache/pip")),
        CacheMountRequest(name="uv-cache", mount_point=Path("/root/.cache/uv")),
        ResolveMountRequest(
            kind="resource",
            resource_id="test_resource",
            mount_point=Path("/data"),
            excludes=[]
        ),
    ]
    
    # Combine schematics
    combined_schematic = schematic + additional_mounts
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=combined_schematic,
        docker_host="zeus"
    )
    
    # Test all components are available
    tests = [
        ("ls -la /data", ["config.yaml", "data.json"]),  # Resource mount
        ("ls -la /root/.cache", ["pip", "uv"]),  # Cache mounts
        ("python -c 'import sys; print(sys.executable)'", ["python"]),  # Python available
    ]
    
    for cmd, expected_items in tests:
        result = await docker_env.run_script(cmd)
        for item in expected_items:
            assert item in result, f"Expected {item} in result of '{cmd}'"
    
    logger.info("✅ Complex multi-project test passed")

# Create IProxy and convert to pytest
test_complex_multi_project_schematics_iproxy: IProxy = a_test_complex_multi_project_schematics(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_complex_multi_project_schematics = to_pytest(test_complex_multi_project_schematics_iproxy)


# ===== Test 4: Schematics with custom components =====
@injected
async def a_test_schematics_custom_components(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test schematics with custom environment components"""
    logger.info("Testing schematics with custom components on Zeus")
    
    # Create custom components
    custom_component1 = EnvComponent(
        installation_macro=["RUN apt-get update && apt-get install -y vim"],
        init_script=["export CUSTOM_VAR1='zeus_test'"]
    )
    
    custom_component2 = EnvComponent(
        installation_macro=["RUN pip install numpy pandas"],
        init_script=["export CUSTOM_VAR2='multi_schematic'"]
    )
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    # Generate schematic with additional components
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim',
        additional_components=[custom_component1, custom_component2]
    )
    
    # Add more customization via ContainerScript
    schematic = schematic + ContainerScript("export FINAL_VAR='zeus_ready'")
    
    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Test custom components
    result = await docker_env.run_script("""
    echo "CUSTOM_VAR1: $CUSTOM_VAR1"
    echo "CUSTOM_VAR2: $CUSTOM_VAR2"
    echo "FINAL_VAR: $FINAL_VAR"
    python -c 'import numpy, pandas; print("Packages installed")'
    which vim
    """)
    
    assert "CUSTOM_VAR1: zeus_test" in result
    assert "CUSTOM_VAR2: multi_schematic" in result
    assert "FINAL_VAR: zeus_ready" in result
    assert "Packages installed" in result
    assert "/usr/bin/vim" in result or "/bin/vim" in result
    
    logger.info("✅ Custom components test passed")

# Create IProxy and convert to pytest
test_schematics_custom_components_iproxy: IProxy = a_test_schematics_custom_components(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_schematics_custom_components = to_pytest(test_schematics_custom_components_iproxy)


# ===== Test 5: Parallel schematics execution =====
@injected
async def a_test_parallel_schematics_execution(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test running multiple Docker environments in parallel on Zeus"""
    logger.info("Testing parallel schematics execution on Zeus")
    
    import asyncio
    
    # Create different project configurations
    projects = [
        ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")]),
        ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")]),
        ProjectDef(dirs=[ProjectDir("test_setuppy", kind="auto")]),
    ]
    
    async def run_env_test(project, index):
        logger.info(f"Starting parallel test {index}")
        
        # Generate schematic
        schematic = await schematics_universal(
            target=project,
            base_image='python:3.11-slim'
        )
        
        # Create Docker environment
        docker_env = new_DockerEnvFromSchematics(
            project=project,
            schematics=schematic,
            docker_host="zeus"
        )
        
        # Run unique command
        result = await docker_env.run_script(f"echo 'Parallel test {index} on Zeus'")
        assert f"Parallel test {index} on Zeus" in result
        
        logger.info(f"✅ Parallel test {index} completed")
        return index
    
    # Run all tests in parallel
    results = await asyncio.gather(*[
        run_env_test(project, i) for i, project in enumerate(projects)
    ])
    
    assert results == [0, 1, 2], "Not all parallel tests completed successfully"
    logger.info("✅ All parallel tests passed")

# Create IProxy and convert to pytest
test_parallel_schematics_execution_iproxy: IProxy = a_test_parallel_schematics_execution(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_parallel_schematics_execution = to_pytest(test_parallel_schematics_execution_iproxy)


# ===== Test 6: Schematics with different Python versions =====
@injected
async def a_test_schematics_python_versions(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test schematics with different Python versions on Zeus"""
    logger.info("Testing different Python versions on Zeus")
    
    python_versions = ["3.9", "3.10", "3.11", "3.12"]
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    
    for py_version in python_versions:
        logger.info(f"Testing Python {py_version}")
        
        # Generate schematic with specific Python version
        schematic = await schematics_universal(
            target=project,
            base_image=f'python:{py_version}-slim',
            python_version=py_version
        )
        
        # Create Docker environment
        docker_env = new_DockerEnvFromSchematics(
            project=project,
            schematics=schematic,
            docker_host="zeus"
        )
        
        # Verify Python version
        result = await docker_env.run_script("python --version")
        assert f"Python {py_version}" in result
        
        logger.info(f"✅ Python {py_version} test passed")

# Create IProxy and convert to pytest
test_schematics_python_versions_iproxy: IProxy = a_test_schematics_python_versions(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_schematics_python_versions = to_pytest(test_schematics_python_versions_iproxy)


# ===== Test 7: Schematics with large file transfers =====
@injected
async def a_test_schematics_large_transfers(schematics_universal, new_DockerEnvFromSchematics, logger, a_system):
    """Test schematics with large file transfers to Zeus"""
    logger.info("Testing large file transfers with Zeus context")
    
    project = ProjectDef(dirs=[ProjectDir("test_source", kind="source")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    # Create a large test file (10MB)
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b'X' * (10 * 1024 * 1024))  # 10MB of data
        test_file = Path(f.name)
    
    try:
        context = docker_env.run_context()
        remote_path = context.random_remote_path()
        
        # Upload large file
        logger.info("Uploading 10MB file to Zeus")
        await context.upload_remote(test_file, remote_path / "large_test.bin")
        
        # Verify file size
        result = await docker_env.run_script(f"ls -lh {remote_path}/large_test.bin | awk '{{print $5}}'")
        assert "10M" in result or "10.0M" in result
        
        # Download back
        logger.info("Downloading 10MB file from Zeus")
        download_path = context.local_download_path / "large_downloaded.bin"
        await context.download_remote(remote_path / "large_test.bin", download_path)
        
        # Verify downloaded file
        assert download_path.exists()
        assert download_path.stat().st_size == 10 * 1024 * 1024
        
        logger.info("✅ Large file transfer test passed")
        
        # Cleanup
        if download_path.exists():
            download_path.unlink()
        await context.delete_remote(remote_path)
        
    finally:
        test_file.unlink()

# Create IProxy and convert to pytest
test_schematics_large_transfers_iproxy: IProxy = a_test_schematics_large_transfers(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger"),
    injected("a_system")
)
test_schematics_large_transfers = to_pytest(test_schematics_large_transfers_iproxy)


# ===== Test 8: Schematics persistence across runs =====
@injected
async def a_test_schematics_persistence(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test that cache mounts persist across runs on Zeus"""
    logger.info("Testing schematics persistence on Zeus")
    
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    # Generate schematic with cache mount
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Add persistent cache
    schematic = schematic + CacheMountRequest(
        name="zeus-persistent-test",
        mount_point=Path("/persistent")
    )
    
    # First run - write data
    docker_env1 = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    await docker_env1.run_script("""
    echo 'Persistent data from Zeus' > /persistent/test.txt
    echo 'Data written'
    """)
    
    # Second run - read data
    docker_env2 = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host="zeus"
    )
    
    result = await docker_env2.run_script("cat /persistent/test.txt")
    assert "Persistent data from Zeus" in result
    
    logger.info("✅ Persistence test passed")

# Create IProxy and convert to pytest
test_schematics_persistence_iproxy: IProxy = a_test_schematics_persistence(
    injected("schematics_universal"), 
    injected("new_DockerEnvFromSchematics"), 
    injected("logger")
)
test_schematics_persistence = to_pytest(test_schematics_persistence_iproxy)


# ===== IProxy entry points for direct execution =====
# These allow running tests directly with pinjected

run_all_zeus_tests: IProxy = injected(lambda logger: logger.info("Run individual tests with pinjected"))()

# Individual test proxies for pinjected execution
zeus_basic: IProxy = test_zeus_context_basic_iproxy
zeus_multi_images: IProxy = test_multiple_schematics_base_images_iproxy
zeus_complex: IProxy = test_complex_multi_project_schematics_iproxy
zeus_custom: IProxy = test_schematics_custom_components_iproxy
zeus_parallel: IProxy = test_parallel_schematics_execution_iproxy
zeus_python_versions: IProxy = test_schematics_python_versions_iproxy
zeus_transfers: IProxy = test_schematics_large_transfers_iproxy
zeus_persistence: IProxy = test_schematics_persistence_iproxy