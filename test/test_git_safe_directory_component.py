"""Test git safe directory component integration in schematics_universal

This test verifies that the git safe directory configuration is properly
included in the generated container schematics.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import EnvComponent
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_source": TEST_PROJECT_ROOT / "test_source",
        "test_resource": TEST_PROJECT_ROOT / "test_resource",
    }
)

# Test design configuration
_design = load_env_design + design(storage_resolver=_storage_resolver, logger=logger)


# ===== Test 1: Git safe directory component structure =====
@injected_pytest(_design)
async def test_git_safe_directory_component_structure(git_safe_directory_component):
    """Test that git_safe_directory_component returns correct structure"""
    component = git_safe_directory_component

    assert isinstance(component, EnvComponent)
    assert component.init_script == ["git config --global --add safe.directory '*'"]
    assert component.installation_macro == []
    assert component.mounts == []
    assert component.dependencies == []


# ===== Test 2: Base apt packages includes git safe directory =====
@injected_pytest(_design)
async def test_base_apt_packages_includes_git_safe_directory(
    base_apt_packages_component, git_safe_directory_component
):
    """Test that base_apt_packages_component includes git_safe_directory_component as dependency"""
    git_safe_comp = git_safe_directory_component
    base_comp = base_apt_packages_component

    assert isinstance(base_comp, EnvComponent)
    assert git_safe_comp in base_comp.dependencies

    # Verify apt packages installation
    assert any(
        "apt-get install" in macro and "git" in macro
        for macro in base_comp.installation_macro
    )


# ===== Test 3: Schematics universal includes git safe directory =====
@injected_pytest(_design)
async def test_schematics_universal_includes_git_safe_directory(
    schematics_universal, logger
):
    """Test that schematics_universal properly includes git safe directory configuration"""
    logger.info("Testing git safe directory inclusion in schematics_universal")

    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    builder = schematic.builder

    # Check scripts for git config command
    scripts_str = " ".join(builder.scripts)
    assert "git config --global --add safe.directory '*'" in scripts_str, (
        "Git safe directory configuration should be in scripts"
    )

    logger.info(f"✅ Git safe directory config found in scripts")


# ===== Test 4: Multiple project types include git safe directory =====
@injected_pytest(_design)
async def test_all_project_types_include_git_safe_directory(
    schematics_universal, logger
):
    """Test that all project types include git safe directory configuration"""
    project_types = [
        ("test_uv", "uv"),
        ("test_rye", "rye"),
        ("test_setuppy", "auto"),
        ("test_requirements", "auto"),
    ]

    for project_id, kind in project_types:
        logger.info(f"Testing {kind} project type for git safe directory")

        project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
        schematic = await schematics_universal(
            target=project, base_image="python:3.11-slim"
        )

        scripts_str = " ".join(schematic.builder.scripts)
        assert "git config --global --add safe.directory '*'" in scripts_str, (
            f"Git safe directory config missing for {kind} project"
        )

        logger.info(f"✅ {kind} project includes git safe directory config")


# ===== Test 5: Component dependencies are properly included =====
@injected_pytest(_design)
async def test_component_dependencies_included(
    base_apt_packages_component,
    git_safe_directory_component,
    logger,
):
    """Test that git_safe_directory_component is included as a dependency"""
    logger.info("Testing component dependencies")

    base_comp = base_apt_packages_component
    git_safe_comp = git_safe_directory_component

    # Check that git_safe_directory_component is in the dependencies
    assert git_safe_comp in base_comp.dependencies, (
        "git_safe_directory_component should be a dependency of base_apt_packages_component"
    )

    # Verify the dependency has the expected init_script
    for dep in base_comp.dependencies:
        if dep == git_safe_comp:
            assert dep.init_script == ["git config --global --add safe.directory '*'"]
            logger.info(
                "✅ git_safe_directory_component found with correct init_script"
            )
            break
