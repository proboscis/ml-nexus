"""Test to verify uv-pip-embed schematic generation content"""

from pathlib import Path
import tempfile
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver


# Create temporary directories for test projects
tmpdir_requirements = tempfile.mkdtemp()
tmppath_requirements = Path(tmpdir_requirements)
test_project_path_requirements = tmppath_requirements / "test_project"
test_project_path_requirements.mkdir()

requirements_file = test_project_path_requirements / "requirements.txt"
requirements_file.write_text("requests==2.31.0\nnumpy==1.26.2\npandas==2.1.4\n")

# Create test design for requirements.txt project
test_design_requirements = load_env_design + design(
    storage_resolver=StaticStorageResolver(
        {"test_uv_pip_project": test_project_path_requirements}
    )
)


tmpdir_setuppy = tempfile.mkdtemp()
tmppath_setuppy = Path(tmpdir_setuppy)
test_project_path_setuppy = tmppath_setuppy / "setup_project"
test_project_path_setuppy.mkdir()

# Create setup.py
(test_project_path_setuppy / "setup.py").write_text("""
from setuptools import setup, find_packages
setup(name="test-package", version="0.1.0", packages=find_packages())
""")

# Create package structure
(test_project_path_setuppy / "test_package").mkdir()
(test_project_path_setuppy / "test_package" / "__init__.py").touch()

# Create test design for setup.py project
test_design_setuppy = load_env_design + design(
    storage_resolver=StaticStorageResolver(
        {"test_setup_project": test_project_path_setuppy}
    )
)


@injected_pytest(test_design_requirements)
async def test_uv_pip_embed_dockerfile_content_requirements(
    schematics_universal, logger
):
    """Test that uv-pip-embed generates correct schematic content for requirements.txt"""
    logger.info("Testing uv-pip-embed with requirements.txt")

    # Create project and generate schematics
    project = ProjectDef(
        dirs=[ProjectDir(id="test_uv_pip_project", kind="uv-pip-embed")]
    )
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Verify builder
    builder = schematics.builder
    assert builder is not None
    assert builder.base_image is not None
    assert builder.macros is not None
    assert builder.scripts is not None

    # Check scripts
    scripts_str = " ".join(builder.scripts)
    assert "uv" in scripts_str or "UV" in scripts_str, "UV commands not found"
    assert "pip" in scripts_str, "pip commands not found"

    logger.info("✅ Requirements.txt project checks passed!")


@injected_pytest(test_design_setuppy)
async def test_uv_pip_embed_dockerfile_content_setuppy(schematics_universal, logger):
    """Test that uv-pip-embed generates correct schematic content for setup.py"""
    logger.info("Testing uv-pip-embed with setup.py")

    # Create project and generate schematics
    project = ProjectDef(
        dirs=[ProjectDir(id="test_setup_project", kind="uv-pip-embed")]
    )
    schematics = await schematics_universal(target=project, python_version="3.12")

    # Verify builder
    builder = schematics.builder
    assert builder is not None

    logger.info("✅ Setup.py project checks passed!")
