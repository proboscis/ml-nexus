"""Integration tests for uv-pip-embed functionality"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver

# Storage resolver for test projects
_dir = Path(__file__).parent / "dummy_projects"
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_requirements": _dir / "test_requirements",
        "test/dummy_projects/test_setuppy": _dir / "test_setuppy",
    }
)

# Test design configuration
_design = load_env_design + design(
    storage_resolver=_storage_resolver, ml_nexus_docker_build_context="zeus"
)


# Test 1: uv-pip-embed with requirements.txt
@injected_pytest(_design)
async def test_uv_pip_embed_requirements(
    schematics_universal, a_PersistentDockerEnvFromSchematics, logger
):
    """Test uv-pip-embed with requirements.txt"""
    logger.info("Testing uv-pip-embed with requirements.txt")

    # Create project
    project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_requirements",
    )

    # Start the container
    await docker_env.start()

    try:
        # Run test script
        result = await docker_env.run_script("""
echo "=== Testing uv-pip-embed with requirements.txt ==="
echo ""
echo "1. Python version:"
python --version
echo ""
echo "2. UV version:"
uv --version
echo ""
echo "3. Which python:"
which python
echo ""
echo "4. Installed packages:"
pip list | grep -E "(requests|numpy)"
echo ""
echo "5. Test imports:"
python -c "
import requests
import numpy as np
print(f'✅ requests {requests.__version__}')
print(f'✅ numpy {np.__version__}')
print('✅ All imports successful!')
"        """)

        logger.info(f"Test result:\n{result}")

        # Verify the test ran successfully
        assert result is not None
        assert "✅ All imports successful!" in result.stdout
        assert "requests" in result.stdout
        assert "numpy" in result.stdout

    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 2: uv-pip-embed with setup.py
@injected_pytest(_design)
async def test_uv_pip_embed_setuppy(
    schematics_universal, a_PersistentDockerEnvFromSchematics, logger
):
    """Test uv-pip-embed with setup.py"""
    logger.info("Testing uv-pip-embed with setup.py")

    # Create project
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="uv-pip-embed")]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.12")

    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_setuppy",
    )

    # Start the container
    await docker_env.start()

    try:
        # Run test script
        result = await docker_env.run_script("""
echo "=== Testing uv-pip-embed with setup.py ==="
echo ""
echo "1. Python version:"
python --version
echo ""
echo "2. UV version:"
uv --version
echo ""
echo "3. Project info:"
pip show test-setuppy
echo ""
echo "4. Test imports:"
python -c "
import requests
import numpy as np
print(f'✅ requests {requests.__version__}')
print(f'✅ numpy {np.__version__}')
print('✅ All imports successful!')
"
        """)

        logger.info(f"Test result:\n{result}")

        # Verify the test ran successfully
        assert result is not None
        assert "✅ All imports successful!" in result.stdout
        assert "requests" in result.stdout
        assert "numpy" in result.stdout

    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 3: Check schematics creation
@injected_pytest(_design)
async def test_check_schematics_info(schematics_universal, logger):
    """Check schematics creation and content"""
    logger.info("Testing schematics creation")

    # Create project
    project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    logger.info(f"=== Schematics Info ===")
    logger.info(f"Base image: {schematics.builder.base_image}")
    logger.info(f"Number of scripts: {len(schematics.builder.scripts)}")
    logger.info(f"Number of macros: {len(schematics.builder.macros)}")

    # Check macro content
    macro_str = str(schematics.builder.macros)
    assert "uv python install" in macro_str, "Missing 'uv python install' in macros"
    logger.info(f"Contains 'uv python install': ✅")

    assert "uv venv" in macro_str, "Missing 'uv venv' in macros"
    logger.info(f"Contains 'uv venv': ✅")

    assert "uv pip install" in macro_str, "Missing 'uv pip install' in macros"
    logger.info(f"Contains 'uv pip install': ✅")

    logger.info("✅ Schematics check complete")
