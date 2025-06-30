"""Test embedded components with actual Docker execution using injected_pytest"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import pytest

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    }
)

# Test design configuration
test_design = load_env_design + design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",
    ml_nexus_default_base_image="python:3.11-slim",
)

# Module design configuration
# __meta_design__ = design(overrides=load_env_design + test_design)  # Removed deprecated __meta_design__


@injected_pytest(test_design)
async def test_uv_auto_embed_execution(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test UV auto-embed Docker container can run Python with dependencies"""
    logger.info("Testing UV auto-embed Docker execution...")

    # Create project
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])

    # Generate schematics
    schematic = await schematics_universal(target=project)

    # Verify no UV cache mounts
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    uv_caches = [m for m in cache_mounts if "uv" in m.cache_name]
    assert len(uv_caches) == 0, f"Found UV cache mounts: {uv_caches}"
    logger.info("✓ No UV cache mounts found")

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Run test script
    result = await docker_env.run_script("""
    set -e
    echo "=== UV Auto-Embed Test ==="
    python --version
    
    echo "--- Testing embedded dependencies ---"
    python -c "
import requests
import pydantic
print(f'✓ requests {requests.__version__}')
print(f'✓ pydantic {pydantic.__version__}')
"
    
    echo "--- Running main.py ---"
    cd /sources/test_uv
    python main.py
    """)

    assert result.exit_code == 0, f"Script failed with exit code {result.exit_code}"
    assert "✓ requests" in result.stdout
    assert "✓ pydantic" in result.stdout
    assert "Hello from UV project!" in result.stdout

    logger.info("✅ UV auto-embed execution test passed")


@injected_pytest(test_design)
async def test_pyvenv_embed_execution(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test pyvenv-embed Docker container can run Python with dependencies"""
    logger.info("Testing pyvenv-embed Docker execution...")

    # Create project
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])

    # Generate schematics
    schematic = await schematics_universal(target=project, python_version="3.11")

    # Verify no pyenv cache mounts
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    pyenv_caches = [
        m for m in cache_mounts if any(x in m.cache_name for x in ["pyenv", "pip"])
    ]
    assert len(pyenv_caches) == 0, f"Found pyenv cache mounts: {pyenv_caches}"
    logger.info("✓ No pyenv/pip cache mounts found")

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Run test script
    result = await docker_env.run_script("""
    set -e
    echo "=== Pyvenv-Embed Test ==="
    python --version
    
    echo "--- Testing embedded dependencies ---"
    python -c "
import requests
import pandas
import numpy
import flask
print(f'✓ requests {requests.__version__}')
print(f'✓ pandas {pandas.__version__}')
print(f'✓ numpy {numpy.__version__}')
print(f'✓ flask {flask.__version__}')
"
    
    echo "--- Testing app.py imports ---"
    cd /sources/test_requirements
    python -c "from app import app; print('✓ Flask app imports successfully')"
    """)

    assert result.exit_code == 0, f"Script failed with exit code {result.exit_code}"
    assert "✓ requests 2.31.0" in result.stdout
    assert "✓ pandas 2.1.4" in result.stdout
    assert "✓ numpy 1.26.2" in result.stdout
    assert "✓ flask 3.0.0" in result.stdout
    assert "✓ Flask app imports successfully" in result.stdout

    logger.info("✅ Pyvenv-embed execution test passed")


@injected_pytest(test_design)
async def test_auto_embed_requirements_execution(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test auto-embed with requirements.txt Docker execution"""
    logger.info("Testing auto-embed requirements.txt Docker execution...")

    # Create project
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto-embed")])

    # Generate schematics
    schematic = await schematics_universal(target=project)

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Run test script
    result = await docker_env.run_script("""
    set -e
    echo "=== Auto-Embed Requirements Test ==="
    python --version
    
    echo "--- Verifying all dependencies ---"
    python -c "
deps = ['requests', 'pandas', 'numpy', 'flask', 'pytest']
for dep in deps:
    mod = __import__(dep)
    print(f'✓ {dep} installed')
"
    """)

    assert result.exit_code == 0, f"Script failed with exit code {result.exit_code}"
    assert "✓ requests installed" in result.stdout
    assert "✓ pandas installed" in result.stdout

    logger.info("✅ Auto-embed requirements.txt execution test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
