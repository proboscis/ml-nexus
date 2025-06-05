"""Best practice example for IProxy tests with pytest

This demonstrates the recommended approach for writing pytest-compatible
IProxy tests in the ml-nexus project.
"""

from pathlib import Path
from pinjected import IProxy, injected, design, injected as injected_dep
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Always import the conversion utility
from test.iproxy_test_utils import to_pytest

# Setup test environment
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

# Configure test-specific dependencies
test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye",
    "test_source": TEST_PROJECT_ROOT / "test_source",
})

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)


# ===== Test 1: Async test example =====
@injected
async def a_test_uv_configuration(schematics_universal, logger):
    """Test UV project configuration generates correct dockerfile components"""
    # Arrange
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    
    # Act
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    # Assert
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    
    assert 'uv sync' in scripts_str, "UV sync command not found in scripts"
    assert len(builder.macros) > 5, f"Expected more than 5 macros, got {len(builder.macros)}"
    assert builder.base_image == 'python:3.11-slim', "Base image mismatch"
    
    logger.info(f"✅ UV configuration test passed with {len(builder.scripts)} scripts")

# Create IProxy and convert for pytest
test_uv_configuration_iproxy: IProxy = a_test_uv_configuration(schematics_universal, logger)
test_uv_configuration = to_pytest(test_uv_configuration_iproxy)


# ===== Test 2: Sync test example =====
@injected
async def a_test_storage_resolver(storage_resolver, logger):
    """Test that our custom storage resolver works correctly"""
    # Test locate method exists
    assert hasattr(storage_resolver, 'locate'), "Storage resolver missing locate method"
    
    # Test we can locate our test projects
    uv_path = await storage_resolver.locate("test_uv")
    assert uv_path.exists(), f"test_uv project path does not exist: {uv_path}"
    assert (uv_path / "pyproject.toml").exists(), "test_uv missing pyproject.toml"
    
    rye_path = await storage_resolver.locate("test_rye")
    assert rye_path.exists(), f"test_rye project path does not exist: {rye_path}"
    
    logger.info("✅ Storage resolver test passed")

# Create IProxy and convert
test_storage_resolver_iproxy: IProxy = a_test_storage_resolver(injected_dep("storage_resolver"), logger)
test_storage_resolver = to_pytest(test_storage_resolver_iproxy)


# ===== Test 3: Parameterized test example =====
@injected
async def a_test_multiple_project_kinds(schematics_universal, logger):
    """Test multiple project kinds in a single test"""
    test_cases = [
        ("test_uv", "uv", "uv sync"),
        ("test_rye", "rye", "rye sync"),
        ("test_source", "source", None),  # Source projects have no sync command
    ]
    
    for project_id, kind, expected_command in test_cases:
        logger.info(f"Testing {kind} project: {project_id}")
        
        project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
        base_image = 'python:3.11-slim' if kind != 'source' else 'ubuntu:22.04'
        
        schematic = await schematics_universal(
            target=project,
            base_image=base_image
        )
        
        scripts_str = ' '.join(schematic.builder.scripts)
        
        if expected_command:
            assert expected_command in scripts_str, f"{expected_command} not found for {kind}"
        else:
            assert len(schematic.builder.scripts) == 0, f"Source project should have no scripts"
        
        logger.info(f"  ✓ {kind} project validated")
    
    logger.info("✅ All project kinds tested successfully")

# Create IProxy and convert
test_multiple_kinds_iproxy: IProxy = a_test_multiple_project_kinds(schematics_universal, logger)
test_multiple_project_kinds = to_pytest(test_multiple_kinds_iproxy)
if __name__ == '__main__':
    pass

# ===== Pattern Summary =====
# 1. Import `to_pytest` utility
# 2. Write test as @injected function  
# 3. Create IProxy: test_name_iproxy = injected_func(deps)
# 4. Convert: test_name = to_pytest(test_name_iproxy)
# 5. pytest discovers and runs `test_name` normally