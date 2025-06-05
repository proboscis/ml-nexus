"""Simple test for schematics_universal with different ProjectDir kinds"""

from pathlib import Path
from pinjected import *
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

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

# Simple function to print basic info about a schematic
@injected
async def a_print_schematic_info(
    schematics_universal,
    /,
    project_id: str,
    kind: str,
    expected_kind: str
):
    """Print basic info about a schematic"""
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing {expected_kind} kind with project: {project_id}")
    logger.info(f"{'='*60}")
    
    project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
    schematic = await schematics_universal(
        target=project,
        base_image='python:3.11-slim' if kind != 'source' else 'ubuntu:22.04'
    )
    
    builder = schematic.builder
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Macros count: {len(builder.macros)}")
    logger.info(f"Scripts count: {len(builder.scripts)}")
    logger.info(f"Mount requests: {len(schematic.mount_requests)}")
    
    # Show first few scripts
    logger.info("\nFirst few scripts:")
    for i, script in enumerate(builder.scripts[:3]):
        logger.info(f"  Script {i}: {script[:60]}...")
    
    return f"Tested {expected_kind} successfully"

# Test each kind
test_uv: IProxy = a_print_schematic_info("test_uv", "uv", "UV")
test_rye: IProxy = a_print_schematic_info("test_rye", "rye", "RYE")
# test_setuppy: IProxy = a_print_schematic_info("test_setuppy", "setup.py", "SETUP.PY")
test_auto: IProxy = a_print_schematic_info("test_requirements", "auto", "AUTO")
test_source: IProxy = a_print_schematic_info("test_source", "source", "SOURCE")
# not covered
# test_resource: IProxy = a_print_schematic_info("test_resource", "resource", "RESOURCE")

# Simple all-in-one test
@injected
async def a_test_all_kinds(schematics_universal):
    """Test all kinds in sequence"""
    test_cases = [
        ("test_uv", "uv", "UV"),
        ("test_rye", "rye", "RYE"),
        ("test_setuppy", "setup.py", "SETUP.PY"),
        ("test_requirements", "auto", "AUTO (requirements.txt)"),
        ("test_source", "source", "SOURCE"),
        ("test_resource", "resource", "RESOURCE"),
    ]
    
    results = []
    for project_id, kind, expected_kind in test_cases:
        result = await a_print_schematic_info(
            schematics_universal, 
            project_id=project_id,
            kind=kind,
            expected_kind=expected_kind
        )
        results.append(result)
    
    logger.info(f"\n{'='*60}")
    logger.info("ALL TESTS COMPLETED")
    logger.info(f"{'='*60}")
    for result in results:
        logger.info(f"✓ {result}")
    
    return results

#test_all: IProxy = a_test_all_kinds(schematics_universal)
if __name__ == '__main__':
    pass

# Design configuration with storage resolver override
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver
    )
)