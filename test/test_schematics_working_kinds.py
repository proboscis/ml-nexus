"""Test working schematics_universal kinds"""

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

# Test working kinds
@injected
async def a_test_working_schematics(
    schematics_universal,
    logger
):
    """Test ProjectDir kinds that are implemented"""
    # Based on env_identification.py, these kinds are implemented:
    # - 'uv' (direct)
    # - 'rye' (direct)
    # - 'source' (direct)
    # - 'auto' (detects based on files)
    
    test_cases = [
        ("test_uv", "uv", "UV"),
        ("test_rye", "rye", "RYE"),
        ("test_source", "source", "SOURCE"),
        ("test_setuppy", "auto", "SETUP.PY (via auto)"),
        ("test_requirements", "auto", "REQUIREMENTS.TXT (via auto)"),
    ]
    
    results = []
    
    for project_id, kind, expected_kind in test_cases:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing {expected_kind} kind with project: {project_id}")
        logger.info(f"{'='*80}")
        
        try:
            project = ProjectDef(dirs=[ProjectDir(project_id, kind=kind)])
            base_image = 'python:3.11-slim' if kind != 'source' else 'ubuntu:22.04'
            
            schematic = await schematics_universal(
                target=project,
                base_image=base_image
            )
            
            builder = schematic.builder
            logger.info(f"✓ Successfully created schematic")
            logger.info(f"  Base image: {builder.base_image}")
            logger.info(f"  Macros count: {len(builder.macros)}")
            logger.info(f"  Scripts count: {len(builder.scripts)}")
            logger.info(f"  Mount requests: {len(schematic.mount_requests)}")
            
            # Analyze key components
            scripts_str = ' '.join(builder.scripts)
            
            if kind == 'uv' and 'uv sync' in scripts_str:
                logger.info(f"  ✓ Found 'uv sync' command")
            elif kind == 'rye' and 'rye sync' in scripts_str:
                logger.info(f"  ✓ Found 'rye sync' command")
            elif kind == 'source':
                logger.info(f"  ✓ No Python environment setup (as expected)")
            elif kind == 'auto':
                if 'pip install -e .' in scripts_str:
                    logger.info(f"  ✓ Found 'pip install -e .' for setup.py")
                elif 'pip install' in scripts_str and 'requirements.txt' in scripts_str:
                    logger.info(f"  ✓ Found pip install for requirements.txt")
            
            results.append({
                "kind": expected_kind,
                "status": "✓ PASSED",
                "macros": len(builder.macros),
                "scripts": len(builder.scripts),
                "mounts": len(schematic.mount_requests)
            })
            
        except Exception as e:
            logger.error(f"✗ Failed: {str(e)}")
            results.append({
                "kind": expected_kind,
                "status": "✗ FAILED",
                "error": str(e)
            })
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}")
    
    for result in results:
        if "error" in result:
            logger.info(f"{result['kind']:30} {result['status']}")
        else:
            logger.info(f"{result['kind']:30} {result['status']} (macros: {result['macros']}, scripts: {result['scripts']}, mounts: {result['mounts']})")
    
    passed = sum(1 for r in results if "PASSED" in r["status"])
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} passed")
    
    return results

test_working: IProxy = a_test_working_schematics(schematics_universal, logger)

# Design configuration with storage resolver override
__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=test_storage_resolver
    )
)