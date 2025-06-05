"""Test UV kind for schematics_universal"""

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
})

# Test UV project
test_uv_project = ProjectDef(dirs=[ProjectDir('test_uv', kind='uv')])
test_uv_schematic: IProxy = schematics_universal(
    target=test_uv_project,
    base_image='python:3.11-slim'
)

# Analyze the UV schematic
@injected
async def a_analyze_uv(schematic):
    """Analyze UV schematic"""
    builder = schematic.builder
    
    logger.info(f"\n{'='*60}")
    logger.info("Analysis for UV kind")
    logger.info(f"{'='*60}")
    
    logger.info(f"Base image: {builder.base_image}")
    logger.info(f"Base stage name: {builder.base_stage_name}")
    logger.info(f"\nMacros count: {len(builder.macros)}")
    
    # Analyze macros
    logger.info("\nMacros breakdown:")
    for i, macro in enumerate(builder.macros):
        if isinstance(macro, str):
            logger.info(f"  Macro {i}: {macro[:80]}...")
        elif isinstance(macro, list):
            logger.info(f"  Macro {i}: List with {len(macro)} items")
            if macro:  # If list is not empty
                if isinstance(macro[0], str):
                    logger.info(f"    First item: {macro[0][:60]}...")
        else:
            logger.info(f"  Macro {i}: {type(macro).__name__}")
    
    # Scripts
    logger.info(f"\nScripts count: {len(builder.scripts)}")
    logger.info("\nScripts:")
    for i, script in enumerate(builder.scripts):
        logger.info(f"  Script {i}: {script}")
    
    # Mount requests
    logger.info(f"\nMount requests: {len(schematic.mount_requests)}")
    for i, mount in enumerate(schematic.mount_requests):
        logger.info(f"  Mount {i}: {mount}")
    
    return "UV analysis complete"

test_analyze: IProxy = a_analyze_uv(test_uv_schematic)

# Design configuration with storage resolver override
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver
    )
)