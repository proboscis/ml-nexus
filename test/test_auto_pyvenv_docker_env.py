"""Test that 'auto' kind projects with requirements.txt or setup.py use pyvenv in DockerEnvFromSchematics

This test verifies that when a project uses kind='auto' and has either requirements.txt
or setup.py, the schematics system correctly sets up a pyvenv environment.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement
from loguru import logger

# Setup test project paths
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Test storage resolver
test_storage_resolver = StaticStorageResolver(
    {
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
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
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",
)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# ===== Test 1: Auto detection with requirements.txt uses pyvenv =====
@injected_pytest(test_design)
async def test_auto_requirements_uses_pyvenv(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test that auto-detected requirements.txt project uses pyvenv"""
    logger.info("Testing auto detection with requirements.txt -> pyvenv")

    # Create project with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto")])

    # Generate schematic
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Verify the schematic uses pyvenv components
    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)
    macros_str = str(builder.macros)

    # Check for pyenv/pyvenv setup indicators
    assert "pip install" in scripts_str, "Should use pip install"
    assert "requirements.txt" in scripts_str, "Should reference requirements.txt"

    # Check for pyenv installation in macros (pyvenv uses pyenv under the hood)
    assert any("pyenv" in str(macro) for macro in builder.macros), (
        "Should have pyenv installation in macros for pyvenv setup"
    )

    logger.info("✅ Requirements.txt auto-detection uses pyvenv")

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test that Python and packages are properly installed
    result = await docker_env.run_script("python --version")
    assert "Python" in result.stdout

    # Test that pandas is installed (from requirements.txt)
    result = await docker_env.run_script(
        "python -c 'import pandas; print(f\"pandas {pandas.__version__}\")'"
    )
    assert "pandas" in result.stdout

    logger.info("✅ Pyvenv environment working correctly with requirements.txt")


# ===== Test 2: Auto detection with setup.py uses pyvenv =====
@injected_pytest(test_design)
async def test_auto_setuppy_uses_pyvenv(
    schematics_universal, new_DockerEnvFromSchematics, logger
):
    """Test that auto-detected setup.py project uses pyvenv"""
    logger.info("Testing auto detection with setup.py -> pyvenv")

    # Create project with auto detection
    project = ProjectDef(dirs=[ProjectDir("test_setuppy", kind="auto")])

    # Generate schematic
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Verify the schematic uses pyvenv components
    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    # Check for pyenv/pyvenv setup indicators
    assert "pip install -e ." in scripts_str, "Should use pip install -e . for setup.py"

    # Check for pyenv installation in macros
    assert any("pyenv" in str(macro) for macro in builder.macros), (
        "Should have pyenv installation in macros for pyvenv setup"
    )

    logger.info("✅ Setup.py auto-detection uses pyvenv")

    # Create Docker environment
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="zeus"
    )

    # Test that Python is properly installed
    result = await docker_env.run_script("python --version")
    assert "Python" in result.stdout

    # Test that the package is installed
    result = await docker_env.run_script(
        "python -c 'import test_setuppy; print(\"test_setuppy imported successfully\")'"
    )
    assert "test_setuppy imported successfully" in result.stdout

    logger.info("✅ Pyvenv environment working correctly with setup.py")


# ===== Test 3: Verify pyvenv vs direct UV/Rye =====
@injected_pytest(test_design)
async def test_pyvenv_differences(schematics_universal, logger):
    """Verify that pyvenv setup is different from UV/Rye"""
    logger.info("Comparing pyvenv setup vs UV/Rye")

    # Create auto-detected project (will use pyvenv)
    auto_project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="auto")])
    auto_schematic = await schematics_universal(
        target=auto_project, base_image="python:3.11-slim"
    )

    # Create UV project for comparison
    uv_project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    uv_schematic = await schematics_universal(
        target=uv_project, base_image="python:3.11-slim"
    )

    # Compare the setups
    auto_scripts = " ".join(auto_schematic.builder.scripts)
    uv_scripts = " ".join(uv_schematic.builder.scripts)

    # Pyvenv uses pip, UV uses uv
    assert "pip install" in auto_scripts, "Pyvenv should use pip"
    assert "uv sync" in uv_scripts, "UV should use uv sync"
    assert "uv sync" not in auto_scripts, "Pyvenv should not use uv"

    logger.info("✅ Confirmed pyvenv setup is different from UV")
