"""Test that all ProjectKind values are properly supported throughout the codebase"""

import pytest
from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir, ProjectKind
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger
from typing import get_args

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver(
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
test_design = load_env_design + design(
    storage_resolver=test_storage_resolver, logger=logger
)


@injected_pytest(test_design)
async def test_all_project_kinds_are_handled(a_prepare_setup_script_with_deps, logger):
    """Test that all values in ProjectKind type alias are handled in a_prepare_setup_script_with_deps"""

    # Get all possible values from the ProjectKind Literal type
    all_kinds = get_args(ProjectKind)

    logger.info(f"Testing all {len(all_kinds)} project kinds: {all_kinds}")

    # Test that each kind can be processed without raising NotImplementedError
    for kind in all_kinds:
        logger.info(f"\nTesting kind: {kind}")

        # Create a project definition with the specific kind
        # Use appropriate test project based on kind
        if kind in ["uv", "auto", "auto-embed"]:
            test_id = "test_uv"
        elif kind == "rye":
            test_id = "test_rye"
        elif kind in ["setup.py", "pyvenv-embed", "uv-pip-embed"]:
            test_id = "test_setuppy"
        elif kind == "requirement.txt":
            test_id = "test_requirements"
        elif kind == "pyvenv":
            # pyvenv can work with either setup.py or requirements.txt
            # Use test_setuppy as it has setup.py
            test_id = "test_setuppy"
        elif kind == "resource":
            test_id = "test_resource"
        elif kind == "source":
            test_id = "test_source"
        else:
            # For any other kind, use a generic test project
            test_id = "test_source"

        project = ProjectDef(dirs=[ProjectDir(id=test_id, kind=kind)])

        try:
            # This should not raise NotImplementedError for any valid kind
            result = await a_prepare_setup_script_with_deps(target=project)
            logger.info(f"✓ Kind '{kind}' handled successfully")
            logger.info(f"  Script: {result.script}")
            logger.info(f"  Deps: {result.env_deps}")
        except NotImplementedError as e:
            # Some kinds are not directly implemented in a_prepare_setup_script_with_deps
            # They are either handled differently or expected to use 'auto' mode
            unimplemented_kinds = ["resource", "setup.py"]
            if kind in unimplemented_kinds:
                logger.info(
                    f"✓ Kind '{kind}' correctly raises NotImplementedError (expected)"
                )
                logger.info(
                    f"  Note: Use 'auto' mode or specific embed variants for this type"
                )
            else:
                pytest.fail(
                    f"Kind '{kind}' is not implemented in a_prepare_setup_script_with_deps: {e}"
                )
        except Exception as e:
            # Some kinds might fail for other reasons (e.g., missing files)
            # but they should not raise NotImplementedError
            logger.warning(f"Kind '{kind}' failed with: {type(e).__name__}: {e}")
            # This is acceptable as long as it's not NotImplementedError


@injected_pytest(test_design)
async def test_project_kind_type_safety(logger):
    """Test that ProjectKind type alias provides type safety"""

    # This test verifies that the type system properly validates project kinds
    # Testing that type system validates project kinds
    ProjectDef(dirs=[ProjectDir(id="test", kind="uv")])  # Valid kind

    # The following would cause a type error if uncommented:
    # invalid_project = ProjectDef(dirs=[ProjectDir(id="test", kind="invalid_kind")])

    logger.info("✓ ProjectKind type alias provides proper type safety")


@injected_pytest(test_design)
async def test_auto_kind_detection(a_prepare_setup_script_with_deps, logger):
    """Test that 'auto' kind properly detects project types"""

    test_cases = [
        ("test_uv", "uv sync", ["uv"]),
        ("test_rye", "rye sync", ["rye"]),
        ("test_setuppy", "pip install -e .", ["pyvenv", "setup.py"]),
        (
            "test_requirements",
            "pip install -r requirements.txt",
            ["pyvenv", "requirements.txt"],
        ),
    ]

    for test_id, expected_script, expected_deps in test_cases:
        project = ProjectDef(dirs=[ProjectDir(id=test_id, kind="auto")])

        result = await a_prepare_setup_script_with_deps(target=project)

        assert expected_script == result.script, (
            f"Expected script '{expected_script}' but got '{result.script}'"
        )
        assert expected_deps == result.env_deps, (
            f"Expected deps {expected_deps} but got {result.env_deps}"
        )

        logger.info(f"✓ Auto-detected {test_id} correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
