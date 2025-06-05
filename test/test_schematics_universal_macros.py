from pathlib import Path
from pinjected import *
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
import json

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

# Test cases for each kind

# 1. UV kind test
test_uv_project = ProjectDef(dirs=[ProjectDir('test_uv', kind='uv')])
test_uv_schematic: IProxy = schematics_universal(
    target=test_uv_project,
    base_image='python:3.11-slim'
)

# 2. Rye kind test  
test_rye_project = ProjectDef(dirs=[ProjectDir('test_rye', kind='rye')])
test_rye_schematic: IProxy = schematics_universal(
    target=test_rye_project,
    base_image='python:3.11-slim'
)

# 3. Setup.py kind test
test_setuppy_project = ProjectDef(dirs=[ProjectDir('test_setuppy', kind='setup.py')])
test_setuppy_schematic: IProxy = schematics_universal(
    target=test_setuppy_project,
    base_image='python:3.11-slim',
    python_version='3.11'
)

# 4. Auto kind test (should detect requirements.txt)
test_auto_project = ProjectDef(dirs=[ProjectDir('test_requirements', kind='auto')])
test_auto_schematic: IProxy = schematics_universal(
    target=test_auto_project,
    base_image='python:3.11-slim'
)

# 5. Source kind test
test_source_project = ProjectDef(dirs=[ProjectDir('test_source', kind='source')])
test_source_schematic: IProxy = schematics_universal(
    target=test_source_project,
    base_image='ubuntu:22.04'
)

# 6. Resource kind test
test_resource_project = ProjectDef(dirs=[ProjectDir('test_resource', kind='resource')])
test_resource_schematic: IProxy = schematics_universal(
    target=test_resource_project,
    base_image='ubuntu:22.04'
)

# Function to analyze and print macros and scripts
@injected
async def a_analyze_schematic(schematic, kind_name: str):
    """Analyze the macros and scripts in a schematic"""
    builder = schematic.builder
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Analysis for {kind_name} kind")
    logger.info(f"{'='*60}")
    
    # Base image
    logger.info(f"Base image: {builder.base_image}")
    
    # Macros (dockerfile instructions)
    logger.info(f"\nMacros count: {len(builder.macros)}")
    for i, macro in enumerate(builder.macros):
        # Handle different macro types
        if isinstance(macro, str):
            logger.info(f"Macro {i}: {macro[:100]}...")
        elif isinstance(macro, list):
            logger.info(f"Macro {i}: List with {len(macro)} items")
            for j, item in enumerate(macro[:3]):  # Show first 3 items
                logger.info(f"  Item {j}: {str(item)[:80]}...")
        else:
            logger.info(f"Macro {i}: {type(macro).__name__}")
    
    # Scripts (entrypoint scripts)
    logger.info(f"\nScripts count: {len(builder.scripts)}")
    for i, script in enumerate(builder.scripts[:5]):  # Show first 5 scripts
        logger.info(f"Script {i}: {script[:80]}...")
    
    # Mount requests
    logger.info(f"\nMount requests: {len(schematic.mount_requests)}")
    for i, mount in enumerate(schematic.mount_requests):
        logger.info(f"Mount {i}: {mount}")
    
    return {
        "kind": kind_name,
        "base_image": builder.base_image,
        "macros_count": len(builder.macros),
        "scripts_count": len(builder.scripts),
        "mounts_count": len(schematic.mount_requests)
    }

# Test runners
test_analyze_uv: IProxy = a_analyze_schematic(test_uv_schematic, kind_name="UV")
test_analyze_rye: IProxy = a_analyze_schematic(test_rye_schematic, kind_name="RYE")
test_analyze_setuppy: IProxy = a_analyze_schematic(test_setuppy_schematic, kind_name="SETUP.PY")
test_analyze_auto: IProxy = a_analyze_schematic(test_auto_schematic, kind_name="AUTO (requirements.txt)")
test_analyze_source: IProxy = a_analyze_schematic(test_source_schematic, kind_name="SOURCE")
test_analyze_resource: IProxy = a_analyze_schematic(test_resource_schematic, kind_name="RESOURCE")

# Run all analyses
test_analyze_all: IProxy = injected.list(
    test_analyze_uv,
    test_analyze_rye,
    test_analyze_setuppy,
    test_analyze_auto,
    test_analyze_source,
    test_analyze_resource
)

# Summary function
@injected
async def a_summarize_results(results):
    """Summarize the test results"""
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY OF ALL TESTS")
    logger.info(f"{'='*60}")
    
    summary_data = []
    for result in results:
        summary_data.append({
            "Kind": result["kind"],
            "Base Image": result["base_image"],
            "Macros": result["macros_count"],
            "Scripts": result["scripts_count"],
            "Mounts": result["mounts_count"]
        })
    
    # Print as table
    logger.info("\n| Kind | Base Image | Macros | Scripts | Mounts |")
    logger.info("|------|------------|--------|---------|--------|")
    for row in summary_data:
        logger.info(f"| {row['Kind']:20} | {row['Base Image']:20} | {row['Macros']:6} | {row['Scripts']:7} | {row['Mounts']:6} |")
    
    return summary_data

test_summary: IProxy = a_summarize_results(test_analyze_all)

# Design configuration with storage resolver override
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver
    )
)