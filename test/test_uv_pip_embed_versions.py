"""Test different Python versions with uv-pip-embed"""

from pathlib import Path
import tempfile
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver


# Create a temporary test project at module level
tmpdir = tempfile.mkdtemp()
tmppath = Path(tmpdir)
test_project_path = tmppath / "test_project"
test_project_path.mkdir()

# Create requirements.txt with version-sensitive packages
requirements_file = test_project_path / "requirements.txt"
requirements_file.write_text("""requests>=2.28.0
numpy>=1.20.0
""")

# Create test script that shows Python version
test_script = test_project_path / "test_version.py"
test_script.write_text("""import sys
import platform
import requests
import numpy as np

print(f"Python version: {sys.version}")
print(f"Python implementation: {platform.python_implementation()}")
print(f"Platform: {platform.platform()}")
print(f"requests version: {requests.__version__}")
print(f"numpy version: {np.__version__}")
""")

# Create test design with storage resolver
test_design = load_env_design + design(
    storage_resolver=StaticStorageResolver({"test_project": test_project_path})
)


# Test 1: Verify schematic generation for different Python versions
@injected_pytest(test_design)
async def test_dockerfile_python_versions(schematics_universal, logger):
    """Test schematic generation for different Python versions"""
    logger.info("Testing schematic generation for different Python versions")

    # Project definition
    project = ProjectDef(dirs=[ProjectDir(id="test_project", kind="uv-pip-embed")])

    # Test Python versions
    versions = ["3.10", "3.11", "3.12", "3.13"]
    schematics_info = {}

    for version in versions:
        logger.info(f"Generating schematic for Python {version}")
        # Call schematics_universal directly with await
        schematics = await schematics_universal(target=project, python_version=version)

        builder = schematics.builder
        assert builder is not None
        assert builder.base_image is not None

        # Get scripts to check for version info
        scripts_str = " ".join(builder.scripts)

        schematics_info[version] = {
            "base_image": builder.base_image,
            "has_uv": "uv" in scripts_str.lower() or "UV" in scripts_str,
            "has_version": version in builder.base_image or version in scripts_str,
        }

        logger.info(f"✅ Python {version} schematic generated")
        logger.info(f"  Base image: {builder.base_image}")

    # Test default version
    logger.info("Generating schematic with default Python version")
    default_schematics = await schematics_universal(target=project)

    # Verify default version also has UV
    default_scripts = " ".join(default_schematics.builder.scripts)
    assert "uv" in default_scripts.lower() or "UV" in default_scripts
    logger.info("✅ Default Python version schematic generated")

    # Verify UV is used in all versions
    for version, info in schematics_info.items():
        assert info["has_uv"], f"Python {version} should use UV"

    logger.info("✅ All Python version schematics verified")


# Test 2: Test actual Python execution with specific version (Docker test)
@injected_pytest(test_design + design(docker_host="zeus"))
async def test_python_311_execution(
    schematics_universal, a_PersistentDockerEnvFromSchematics, logger
):
    """Test Python 3.11 execution with uv-pip-embed"""
    logger.info("Testing Python 3.11 execution with uv-pip-embed")

    # Project definition
    project = ProjectDef(dirs=[ProjectDir(id="test_project", kind="uv-pip-embed")])

    # Generate schematics for Python 3.11
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Create Docker environment
    docker_env = await a_PersistentDockerEnvFromSchematics(
        project=project,
        schematics=schematics,
        docker_host="zeus",
        container_name="test_uv_pip_embed_py311",
    )

    # Start container
    await docker_env.start()

    try:
        # Run test script
        result = await docker_env.run_script("""
echo "=== Testing Python 3.11 with uv-pip-embed ==="
python --version
echo "---"
python test_version.py
echo "---"
which python
echo "---"
uv --version
""")

        logger.info(f"Test result:\n{result.stdout}")

        # Verify the test ran successfully
        assert result.exit_code == 0
        assert "Python 3.11" in result.stdout
        assert "requests version:" in result.stdout
        assert "numpy version:" in result.stdout
        assert "uv" in result.stdout.lower()

    finally:
        # Clean up
        try:
            await docker_env.stop()
        except Exception as e:
            logger.warning(f"Failed to stop container: {e}")


# Test 3: Compare Python versions
@injected_pytest(test_design)
async def test_compare_python_versions(schematics_universal, logger):
    """Compare schematics generation across Python versions"""
    logger.info("Comparing schematics generation across Python versions")

    # Project definition
    project = ProjectDef(dirs=[ProjectDir(id="test_project", kind="uv-pip-embed")])

    # Generate schematics for different versions
    versions_info = {}

    for version in ["3.10", "3.11", "3.12", "3.13"]:
        schematics = await schematics_universal(target=project, python_version=version)

        builder = schematics.builder
        entrypoint_script = await builder.a_entrypoint_script()
        scripts_str = " ".join(builder.scripts)

        versions_info[version] = {
            "script_lines": len(entrypoint_script.split("\n")),
            "has_uv": "uv" in scripts_str.lower() or "UV" in scripts_str,
            "has_python_version": version in builder.base_image
            or version in scripts_str
            or version in entrypoint_script,
            "base_image": builder.base_image,
        }

        logger.info(f"Python {version}: {versions_info[version]}")

    # Verify all versions use UV
    for version, info in versions_info.items():
        assert info["has_uv"], f"Python {version} should use UV"
        # Note: Python version might be in base image or scripts
        logger.info(f"Python {version} base image: {info['base_image']}")

    logger.info("✅ Python version comparison complete")


# Test 4: Test multiple Python versions with Docker
@injected_pytest(test_design + design(docker_host="zeus"))
async def test_multiple_python_versions_docker(
    schematics_universal, a_PersistentDockerEnvFromSchematics, logger
):
    """Test multiple Python versions (3.10-3.13) with Docker"""
    logger.info("Testing multiple Python versions with Docker")

    # Project definition
    project = ProjectDef(dirs=[ProjectDir(id="test_project", kind="uv-pip-embed")])

    # Test each Python version
    for version in ["3.10", "3.11", "3.12", "3.13"]:
        logger.info(f"Testing Python {version} with Docker")

        # Generate schematics for this version
        schematics = await schematics_universal(target=project, python_version=version)

        # Create Docker environment
        docker_env = await a_PersistentDockerEnvFromSchematics(
            project=project,
            schematics=schematics,
            docker_host="zeus",
            container_name=f"test_uv_pip_embed_py{version.replace('.', '')}",
        )

        # Start container
        await docker_env.start()

        try:
            # Run test script
            result = await docker_env.run_script(f"""
echo "=== Testing Python {version} with uv-pip-embed ==="
python --version
echo "---"
python test_version.py
echo "---"
which python
echo "---"
pip --version
echo "=== Test complete ==="
""")

            logger.info(f"Test result for Python {version}:\n{result.stdout}")

            # Verify the test ran successfully
            assert result.exit_code == 0
            assert f"Python {version}" in result.stdout
            assert "requests version:" in result.stdout
            assert "numpy version:" in result.stdout

            logger.info(f"✅ Python {version} test passed")

        finally:
            # Clean up
            try:
                await docker_env.stop()
            except Exception as e:
                logger.warning(f"Failed to stop container for Python {version}: {e}")
