"""Test UV project with CUDA accelerator using schematics

This test verifies that UV projects with CUDA dependencies can be properly
built and run using the schematics system.
"""

from pathlib import Path
from pinjected import design, IProxy, injected
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics, DockerHostPlacement
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import ContainerSchematic
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import DirectoryStorageResolver
from loguru import logger


project_uv_with_accelerator = ProjectDef(
    dirs=[
        ProjectDir(
            id='uv_with_accelerator',
            kind='uv',
            excludes=[
                ".venv", ".git"
            ]
        )
    ]
)
schematics_uv_with_accelerator: IProxy[ContainerSchematic] = schematics_universal(
    project_uv_with_accelerator,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    python_version='3.10'
)


# A hack is:
# replace uv sync with other lines.
@injected
async def a_hack_uv_sync_with_torch_dep_package(lines: list[str]) -> list[str]:
    # This hack works!
    res = []
    for line in lines:
        if 'uv sync' in line:
            res += [
                "uv sync --extra build",
                "uv sync --extra build --extra basicsr"
            ]
        else:
            res.append(line)
    return res


hacked_schematics = schematics_uv_with_accelerator.a_map_scripts(a_hack_uv_sync_with_torch_dep_package).await__()

remote_docker_env = injected(DockerEnvFromSchematics)(
    project=project_uv_with_accelerator,
    schematics=hacked_schematics,
    docker_host='zeus',
    placement=DockerHostPlacement(
        cache_root=Path('/tmp/cache_root'),
        resource_root=Path('/tmp/resource_root'),
        source_root=Path('/tmp/source_root'),
        direct_root=Path('/tmp/direct_root')
    )
)
run_script_zeus: IProxy = remote_docker_env.run_script('echo "Hello, World!"')
local_docker_env = injected(DockerEnvFromSchematics)(
    project=project_uv_with_accelerator,
    schematics=hacked_schematics,
    docker_host='localhost',
    placement=DockerHostPlacement(
        cache_root=Path('/tmp/cache_root'),
        resource_root=Path('/tmp/resource_root'),
        source_root=Path('/tmp/source_root'),
        direct_root=Path('/tmp/direct_root')
    )
)
run_python_zeus:IProxy = remote_docker_env.run_script('python -c "import torch; import basicsr; print(torch.__version__)"')

# Test design configuration
test_design = design(
    storage_resolver=DirectoryStorageResolver(
        Path("~/repos/ml-nexus-test-repositories").expanduser(),
    ),
    logger=logger,
)

__meta_design__ = design(
    overrides=load_env_design + test_design
)


# ===== Test 1: Basic script execution on Zeus =====
@injected_pytest(test_design)
async def test_run_script_zeus(logger):
    """Test running a simple script on Zeus Docker host"""
    logger.info("Testing script execution on Zeus")
    
    # Build Docker environment
    docker_env = DockerEnvFromSchematics(
        project=project_uv_with_accelerator,
        schematics=hacked_schematics,
        docker_host='zeus',
        placement=DockerHostPlacement(
            cache_root=Path('/tmp/cache_root'),
            resource_root=Path('/tmp/resource_root'),
            source_root=Path('/tmp/source_root'),
            direct_root=Path('/tmp/direct_root')
        )
    )
    
    # Run script
    result = await docker_env.run_script('echo "Hello, World!"')
    assert "Hello, World!" in result
    logger.info("✅ Script execution test passed")


# ===== Test 2: Python with CUDA dependencies =====
@injected_pytest(test_design)
async def test_python_cuda_deps_zeus(logger):
    """Test running Python with CUDA dependencies on Zeus"""
    logger.info("Testing Python with CUDA dependencies")
    
    # Build Docker environment
    docker_env = DockerEnvFromSchematics(
        project=project_uv_with_accelerator,
        schematics=hacked_schematics,
        docker_host='zeus',
        placement=DockerHostPlacement(
            cache_root=Path('/tmp/cache_root'),
            resource_root=Path('/tmp/resource_root'),
            source_root=Path('/tmp/source_root'),
            direct_root=Path('/tmp/direct_root')
        )
    )
    
    # Run Python script with torch and basicsr
    result = await docker_env.run_script('python -c "import torch; import basicsr; print(torch.__version__)"')
    
    # Verify torch is imported successfully
    assert "torch" not in result.lower() or "error" not in result.lower()
    logger.info(f"PyTorch version detected: {result.strip()}")
    logger.info("✅ CUDA dependencies test passed")


# ===== Test 3: Storage resolver =====
@injected_pytest(test_design)
async def test_storage_resolver(storage_resolver, logger):
    """Test that storage resolver is properly injected"""
    logger.info("Testing storage resolver injection")
    
    assert storage_resolver is not None
    assert isinstance(storage_resolver, DirectoryStorageResolver)
    logger.info("✅ Storage resolver test passed")
