"""Example of converting IProxy tests to pytest-compatible functions

This demonstrates how to use the pytest_iproxy_adapter to make
IProxy test objects work with pytest.
"""

from pathlib import Path
from pinjected import IProxy
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Import the adapter
from test.pytest_iproxy_adapter import as_pytest_test, convert_module_iproxy_tests

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver({
    "test_uv": TEST_PROJECT_ROOT / "test_uv",
    "test_rye": TEST_PROJECT_ROOT / "test_rye", 
    "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    "test_source": TEST_PROJECT_ROOT / "test_source",
    "test_resource": TEST_PROJECT_ROOT / "test_resource",
})

# Design configuration
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver,
        logger=logger
    )
)

# Method 1: Manual conversion with decorator
@injected
async def a_test_uv_kind(schematics_universal, logger):
    """Test UV ProjectDir kind"""
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    
    assert 'uv sync' in scripts_str, "UV sync command not found"
    logger.info(f"✓ UV test passed - found {len(builder.scripts)} scripts")
    return True

# Convert IProxy to pytest function manually
test_uv_manual = as_pytest_test(a_test_uv_kind(schematics_universal, logger))


# Method 2: Define IProxy objects and convert at module level
@injected
async def a_test_rye_kind(schematics_universal, logger):
    """Test RYE ProjectDir kind"""
    project = ProjectDef(dirs=[ProjectDir("test_rye", kind="rye")])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim'
    )
    
    builder = schematic.builder
    scripts_str = ' '.join(builder.scripts)
    
    assert 'rye sync' in scripts_str, "Rye sync command not found"
    logger.info(f"✓ RYE test passed - found {len(builder.scripts)} scripts")
    return True

# Create IProxy objects
test_uv_iproxy: IProxy = a_test_uv_kind(schematics_universal, logger)
test_rye_iproxy: IProxy = a_test_rye_kind(schematics_universal, logger)

# Method 3: Convert all at once at module import
# This converts all test_* IProxy objects to pytest functions
_converted_tests = convert_module_iproxy_tests(__file__)
for name, func in _converted_tests.items():
    globals()[name] = func

# Now pytest can discover and run these tests normally!
# Run with: pytest test_schematics_pytest_compatible.py