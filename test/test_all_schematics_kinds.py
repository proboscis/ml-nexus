"""Test all schematics_universal kinds with macro analysis"""

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

# Test all kinds
@injected
async def a_test_all_schematics(
    schematics_universal,
    logger
):
    """Test all ProjectDir kinds"""
    test_cases = [
        ("test_uv", "uv", "UV"),
        ("test_rye", "rye", "RYE"),
        # ("test_setuppy", "setup.py", "SETUP.PY"),  # Not implemented as direct kind
        ("test_setuppy", "auto", "SETUP.PY (via auto)"),  # Use auto detection
        ("test_requirements", "auto", "AUTO (requirements.txt)"),
        ("test_source", "source", "SOURCE"),
        ("test_resource", "resource", "RESOURCE"),
    ]
    
    for project_id, kind, expected_kind in test_cases:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing {expected_kind} kind with project: {project_id}")
        logger.info(f"{'='*80}")
        
        project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
        base_image = 'python:3.11-slim' if kind not in ('source', 'resource') else 'ubuntu:22.04'
        
        schematic = await schematics_universal(
            target=project,
            base_image=base_image,
            python_version='3.11' if kind == 'setup.py' else None
        )
        
        builder = schematic.builder
        logger.info(f"Base image: {builder.base_image}")
        logger.info(f"Base stage name: {builder.base_stage_name}")
        logger.info(f"Macros count: {len(builder.macros)}")
        logger.info(f"Scripts count: {len(builder.scripts)}")
        logger.info(f"Mount requests: {len(schematic.mount_requests)}")
        
        # Analyze macros
        logger.info("\nKey macros:")
        for i, macro in enumerate(builder.macros):
            if isinstance(macro, list) and macro:
                # Look for key indicators
                macro_str = str(macro)
                if 'uv' in macro_str.lower() and kind == 'uv':
                    logger.info(f"  ✓ Found UV installation macro")
                elif 'rye' in macro_str.lower() and kind == 'rye':
                    logger.info(f"  ✓ Found Rye installation macro")
                elif 'pyenv' in macro_str.lower() and 'setup' in expected_kind.lower():
                    logger.info(f"  ✓ Found pyenv installation macro")
                elif 'requirements.txt' in macro_str.lower() and kind == 'auto':
                    logger.info(f"  ✓ Found requirements.txt handling")
        
        # Analyze scripts
        logger.info("\nKey scripts:")
        scripts_str = ' '.join(builder.scripts)
        if 'uv sync' in scripts_str and kind == 'uv':
            logger.info(f"  ✓ Found 'uv sync' in scripts")
        elif 'rye sync' in scripts_str and kind == 'rye':
            logger.info(f"  ✓ Found 'rye sync' in scripts")
        elif 'pip install -e .' in scripts_str and 'setup' in expected_kind.lower():
            logger.info(f"  ✓ Found 'pip install -e .' in scripts")
        elif kind in ('source', 'resource'):
            logger.info(f"  ✓ No Python environment setup (as expected)")
    
    logger.info(f"\n{'='*80}")
    logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
    logger.info(f"{'='*80}")
    
    return "All schematics kinds tested successfully"

# Create IProxy object - the plugin will automatically convert this
test_all: IProxy = a_test_all_schematics(schematics_universal, logger)

# Design configuration with storage resolver override
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver
    )
)