"""Best practice example for tests with @injected_pytest decorator

This demonstrates the recommended approach for writing pytest-compatible
tests using the @injected_pytest decorator in the ml-nexus project.
"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Setup test environment
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Configure test-specific dependencies
test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_rye": TEST_PROJECT_ROOT / "test_rye",
        "test_source": TEST_PROJECT_ROOT / "test_source",
    }
)

# Test design configuration
test_design = design(storage_resolver=test_storage_resolver, logger=logger)

# Module design configuration
__meta_design__ = design(overrides=load_env_design + test_design)


# ===== Test 1: Async test example =====
@injected_pytest(test_design)
async def test_uv_configuration(schematics_universal, logger):
    """Test UV project configuration generates correct dockerfile components"""
    # Arrange
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])

    # Act
    schematic = await schematics_universal(
        target=project, base_image="python:3.11-slim"
    )

    # Assert
    builder = schematic.builder
    scripts_str = " ".join(builder.scripts)

    assert "uv sync" in scripts_str, "UV sync command not found in scripts"
    assert len(builder.macros) > 5, (
        f"Expected more than 5 macros, got {len(builder.macros)}"
    )
    assert builder.base_image == "python:3.11-slim", "Base image mismatch"

    logger.info(f"✅ UV configuration test passed with {len(builder.scripts)} scripts")


# ===== Test 2: Storage resolver test example =====
@injected_pytest(test_design)
async def test_storage_resolver(storage_resolver, logger):
    """Test that our custom storage resolver works correctly"""
    # Test locate method exists
    assert hasattr(storage_resolver, "locate"), "Storage resolver missing locate method"

    # Test we can locate our test projects
    uv_path = await storage_resolver.locate("test_uv")
    assert uv_path.exists(), f"test_uv project path does not exist: {uv_path}"
    assert (uv_path / "pyproject.toml").exists(), "test_uv missing pyproject.toml"

    rye_path = await storage_resolver.locate("test_rye")
    assert rye_path.exists(), f"test_rye project path does not exist: {rye_path}"

    logger.info("✅ Storage resolver test passed")


# ===== Test 3: Parameterized test example =====
@injected_pytest(test_design)
async def test_multiple_project_kinds(schematics_universal, logger):
    """Test multiple project kinds in a single test"""
    test_cases = [
        ("test_uv", "uv", "uv sync"),
        ("test_rye", "rye", "rye sync"),
        ("test_source", "source", None),  # Source projects have no sync command
    ]

    for project_id, kind, expected_command in test_cases:
        logger.info(f"Testing {kind} project: {project_id}")

        project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
        base_image = "python:3.11-slim" if kind != "source" else "ubuntu:22.04"

        schematic = await schematics_universal(target=project, base_image=base_image)

        scripts_str = " ".join(schematic.builder.scripts)

        if expected_command:
            assert expected_command in scripts_str, (
                f"{expected_command} not found for {kind}"
            )
        else:
            assert len(schematic.builder.scripts) == 0, (
                "Source project should have no scripts"
            )

        logger.info(f"  ✓ {kind} project validated")

    logger.info("✅ All project kinds tested successfully")


# ===== Pattern Summary =====
# 1. Import `from pinjected.test import injected_pytest`
# 2. Create test_design with test-specific bindings
# 3. Write test with @injected_pytest(test_design) decorator
# 4. Test function name must start with 'test_' for pytest discovery
# 5. pytest discovers and runs tests normally
