"""Test working schematics_universal kinds using @injected_pytest"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
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

# Test design configuration
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger
)

# Module design configuration
__meta_design__ = design(
    overrides=load_env_design + test_design
)


# Test working kinds
@injected_pytest(test_design)
async def test_working_schematics(
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
            logger.info("✓ Successfully created schematic")
            logger.info(f"  Base image: {builder.base_image}")
            logger.info(f"  Macros count: {len(builder.macros)}")
            logger.info(f"  Scripts count: {len(builder.scripts)}")
            logger.info(f"  Mount requests: {len(schematic.mount_requests)}")
            
            # Analyze key components
            scripts_str = ' '.join(builder.scripts)
            
            if kind == 'uv' and 'uv sync' in scripts_str:
                logger.info("  ✓ Found 'uv sync' command")
            elif kind == 'rye' and 'rye sync' in scripts_str:
                logger.info("  ✓ Found 'rye sync' command")
            elif kind == 'source':
                logger.info("  ✓ No Python environment setup (as expected)")
            elif kind == 'auto':
                if 'pip install -e .' in scripts_str:
                    logger.info("  ✓ Found 'pip install -e .' for setup.py")
                elif 'pip install' in scripts_str and 'requirements.txt' in scripts_str:
                    logger.info("  ✓ Found pip install for requirements.txt")
            
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
    
    # Assert all tests passed
    assert passed == total, f"Only {passed}/{total} tests passed"
    
    # Additional assertions for each test case
    for result in results:
        assert result["status"] == "✓ PASSED", f"{result['kind']} failed: {result.get('error', 'Unknown error')}"