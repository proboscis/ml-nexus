"""Test to verify uv-pip-embed functionality"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Configure static resolver for test directories
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_requirements": Path(__file__).parent
        / "dummy_projects"
        / "test_requirements",
        "test/dummy_projects/test_setuppy": Path(__file__).parent
        / "dummy_projects"
        / "test_setuppy",
    }
)

# Test design configuration
_design = load_env_design + design(
    storage_resolver=_storage_resolver,
    ml_nexus_docker_build_context="zeus",
    logger=logger,
    docker_command_info="",  # Add docker_command_info
)


# Test 1: uv-pip-embed project with requirements.txt
@injected_pytest(_design)
async def test_uv_pip_embed_requirements(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test uv-pip-embed functionality with requirements.txt"""
    logger.info("Testing uv-pip-embed with requirements.txt")

    # Create project definition
    project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Create Docker environment
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_requirements",
    )

    # Ensure container is running
    await docker_env.ensure_container()

    try:
        # Run test script
        result = await docker_env.run_script(
            """
echo "Testing uv-pip-embed project with requirements.txt"
echo "---"
echo "Python version:"
python --version
echo "---"
echo "UV version:"
uv --version
echo "---"
echo "Installed packages:"
pip list
echo "---"
echo "Which python:"
which python
echo "---"
echo "Testing imports:"
python -c "import requests; print(f'requests version: {requests.__version__}')"
python -c "import pandas; print(f'pandas version: {pandas.__version__}')"
python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
"""
        )

        logger.info(f"Test result:\n{result.stdout}")

        # Verify the test ran successfully
        assert result is not None
        assert "requests version:" in result.stdout
        assert "pandas version:" in result.stdout
        assert "numpy version:" in result.stdout

    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 2: uv-pip-embed project with setup.py
@injected_pytest(_design)
async def test_uv_pip_embed_setuppy(
    schematics_universal, new_PersistentDockerEnvFromSchematics, logger
):
    """Test uv-pip-embed functionality with setup.py"""
    logger.info("Testing uv-pip-embed with setup.py")

    # Create project definition
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="uv-pip-embed")]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Create Docker environment
    docker_env = new_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_setuppy",
    )

    # Ensure container is running
    await docker_env.ensure_container()

    try:
        # Run test script
        result = await docker_env.run_script(
            """
echo "Testing uv-pip-embed project with setup.py"
echo "---"
echo "Python version:"
python --version
echo "---"
echo "UV version:"
uv --version
echo "---"
echo "Installed packages:"
pip list
echo "---"
echo "Which python:"
which python
echo "---"
echo "Testing imports:"
python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
python -c "import pandas; print(f'pandas version: {pandas.__version__}')"
python -c "import test_setuppy; print('test_setuppy imported successfully')"
"""
        )

        logger.info(f"Test result:\n{result.stdout}")

        # Verify the test ran successfully
        assert result is not None
        assert "numpy version:" in result.stdout
        assert "pandas version:" in result.stdout
        assert "test_setuppy imported successfully" in result.stdout

    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")
