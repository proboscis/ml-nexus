"""Test different ProjectDir kinds with schematics_universal and DockerEnvFromSchematics"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"
REPO_ROOT = Path(__file__).parent.parent

test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
    "test_resource": TEST_PROJECT_ROOT / "test_resource",
    # Add mappings for actual directories used in tests
    "ml_nexus": REPO_ROOT,  # For the current project root
    "src/ml_nexus": REPO_ROOT / "src" / "ml_nexus",
    "doc": REPO_ROOT / "doc",
})

# Test design configuration
test_design = design(
    docker_host='zeus',
    storage_resolver=test_storage_resolver,
    logger=logger
)

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + test_design
)


# Test source kind - no Python environment
@injected_pytest(test_design)
async def test_source_kind(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test source kind with no Python environment"""
    project = ProjectDef(dirs=[ProjectDir('test_source', kind='source')])
    
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host='zeus'
    )
    
    result = await docker_env.run_script("""
    echo "Testing source kind - no Python environment"
    ls -la
    pwd
    """)
    
    assert "Testing source kind" in result.stdout
    assert result.exit_code == 0
    logger.info("✅ Source kind test passed")

# Test resource kind
@injected_pytest(test_design)
async def test_resource_kind(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test resource kind for mounting resources"""
    project = ProjectDef(dirs=[ProjectDir('test_resource', kind='resource')])
    
    schematic = await schematics_universal(
        target=project,
        base_image='ubuntu:22.04'
    )
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host='zeus'
    )
    
    result = await docker_env.run_script("""
    echo "Testing resource kind"
    ls -la /resources/ || echo "Resources directory not found"
    """)
    
    assert "Testing resource kind" in result.stdout
    logger.info("✅ Resource kind test passed")

# Test auto kind - will auto-detect project type
@injected_pytest(test_design)
async def test_auto_kind(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test auto kind that auto-detects project type"""
    # Using test UV project which has pyproject.toml
    project = ProjectDef(dirs=[ProjectDir('test_uv', kind='auto')])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host='zeus'
    )
    
    result = await docker_env.run_script("""
    echo "Testing auto kind"
    which python
    python --version
    """)
    
    assert "Testing auto kind" in result.stdout
    assert "Python" in result.stdout
    logger.info("✅ Auto kind test passed")

# Test UV kind with persistent container
@injected_pytest(test_design)
async def test_uv_kind_persistent(schematics_universal, new_PersistentDockerEnvFromSchematics, logger):
    """Test UV kind with persistent Docker container"""
    project = ProjectDef(dirs=[ProjectDir('test_uv', kind='uv')])
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host='zeus',
        container_name='test_uv_kind_pytest'
    )
    
    try:
        result = await docker_env.run_script("""
        echo "Testing UV kind"
        which uv || echo "UV not found"
        python --version
        """)
        
        assert "Testing UV kind" in result.stdout
        assert "Python" in result.stdout
        logger.info("✅ UV kind test passed")
    finally:
        # Clean up persistent container
        try:
            await docker_env.stop()
        except Exception:
            pass

# Test mixed kinds - UV + resource
@injected_pytest(test_design)
async def test_mixed_kinds(schematics_universal, new_DockerEnvFromSchematics, logger):
    """Test mixed project with UV and resource kinds"""
    project = ProjectDef(
        dirs=[
            ProjectDir('test_uv', kind='uv'),
            ProjectDir('test_resource', kind='resource'),
        ]
    )
    
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    docker_env = new_DockerEnvFromSchematics(
        project=project,
        schematics=schematic,
        docker_host='zeus'
    )
    
    result = await docker_env.run_script("""
    echo "Testing mixed kinds"
    ls -la /sources/ || echo "Sources not found"
    ls -la /resources/ || echo "Resources not found"
    python --version
    """)
    
    assert "Testing mixed kinds" in result.stdout
    assert "Python" in result.stdout
    logger.info("✅ Mixed kinds test passed")


# Test with GPU base image
@injected_pytest(test_design)
async def test_gpu_base_image(schematics_universal, logger):
    """Test schematics with GPU base image"""
    project = ProjectDef(dirs=[ProjectDir('test_uv', kind='uv')])
    
    schematic = await schematics_universal(
        target=project,
        base_image='nvidia/cuda:12.3.1-devel-ubuntu22.04',
        python_version='3.11'
    )
    
    # Just verify the schematic is created correctly
    assert schematic.builder.base_image == 'nvidia/cuda:12.3.1-devel-ubuntu22.04'
    assert len(schematic.builder.macros) > 0
    logger.info("✅ GPU base image test passed")