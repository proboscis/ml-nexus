"""Test to verify uv-pip-embed schematic generation"""

from pathlib import Path
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger

# Configure static resolver for test directories
_storage_resolver = StaticStorageResolver(
    {
        "test/dummy_projects/test_requirements": Path(__file__).parent
        / "dummy_projects"
        / "test_requirements",
        "test/dummy_projects/test_setuppy": Path(__file__).parent
        / "dummy_projects"
        / "test_setuppy",
    }
)

# Test design configuration
_design = load_env_design + design(storage_resolver=_storage_resolver, logger=logger)


# Test 1: uv-pip-embed schematic generation with requirements.txt
@injected_pytest(_design)
async def test_uv_pip_embed_dockerfile_requirements(schematics_universal, logger):
    """Test schematic generation for uv-pip-embed with requirements.txt"""
    logger.info("Testing uv-pip-embed schematic generation with requirements.txt")

    # Create project
    project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Verify builder components
    builder = schematics.builder
    assert builder is not None
    assert builder.base_image is not None
    assert len(builder.macros) > 0
    assert len(builder.scripts) > 0

    # Get entrypoint script to verify UV commands
    entrypoint_script = await builder.a_entrypoint_script()

    logger.info(f"Generated entrypoint script:\n{entrypoint_script[:500]}...")

    # Verify script content
    assert entrypoint_script is not None
    assert len(entrypoint_script) > 0

    # Check for UV-specific commands in scripts
    scripts_str = " ".join(builder.scripts)
    assert "uv" in scripts_str or "UV" in scripts_str
    assert "pip" in scripts_str

    logger.info("✅ uv-pip-embed schematic with requirements.txt verified")


# Test 2: uv-pip-embed schematic generation with setup.py
@injected_pytest(_design)
async def test_uv_pip_embed_dockerfile_setuppy(schematics_universal, logger):
    """Test schematic generation for uv-pip-embed with setup.py"""
    logger.info("Testing uv-pip-embed schematic generation with setup.py")

    # Create project
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="uv-pip-embed")]
    )

    # Generate schematics
    schematics = await schematics_universal(target=project, python_version="3.11")

    # Verify builder components
    builder = schematics.builder
    assert builder is not None
    assert builder.base_image is not None
    assert len(builder.macros) > 0
    assert len(builder.scripts) > 0

    # Get entrypoint script to verify UV commands
    entrypoint_script = await builder.a_entrypoint_script()

    logger.info(f"Generated entrypoint script:\n{entrypoint_script[:500]}...")

    # Verify script content
    assert entrypoint_script is not None
    assert len(entrypoint_script) > 0

    # Check for setup.py installation in scripts
    scripts_str = " ".join(builder.scripts)
    assert "uv" in scripts_str or "UV" in scripts_str
    assert "pip" in scripts_str or "setup.py" in scripts_str

    logger.info("✅ uv-pip-embed schematic with setup.py verified")


# Test 3: Compare schematics between requirements.txt and setup.py
@injected_pytest(_design)
async def test_compare_uv_pip_embed_dockerfiles(schematics_universal, logger):
    """Compare schematic generation between requirements.txt and setup.py projects"""
    logger.info("Comparing uv-pip-embed schematics")

    # Create projects
    req_project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )
    setup_project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="uv-pip-embed")]
    )

    # Generate schematics
    req_schematics = await schematics_universal(
        target=req_project, python_version="3.11"
    )
    setup_schematics = await schematics_universal(
        target=setup_project, python_version="3.11"
    )

    # Get builders
    req_builder = req_schematics.builder
    setup_builder = setup_schematics.builder

    # Get entrypoint scripts
    req_script = await req_builder.a_entrypoint_script()
    setup_script = await setup_builder.a_entrypoint_script()

    logger.info(f"Requirements.txt script: {len(req_script)} chars")
    logger.info(f"Setup.py script: {len(setup_script)} chars")

    # Both should use UV
    req_scripts_str = " ".join(req_builder.scripts)
    setup_scripts_str = " ".join(setup_builder.scripts)

    assert "uv" in req_scripts_str.lower() or "UV" in req_scripts_str
    assert "uv" in setup_scripts_str.lower() or "UV" in setup_scripts_str

    # Requirements.txt specific
    assert "requirements.txt" in req_scripts_str or "requirements.txt" in req_script

    # Setup.py specific
    assert "setup.py" in setup_scripts_str or "pip install" in setup_script

    logger.info("✅ Schematic comparison complete")


# Test 4: Test Python versions 3.10-3.13 with requirements.txt
@injected_pytest(_design)
async def test_uv_pip_embed_python_versions_requirements(schematics_universal, logger):
    """Test uv-pip-embed with Python 3.10-3.13 for requirements.txt project"""
    logger.info("Testing uv-pip-embed with Python 3.10-3.13 (requirements.txt)")

    # Create project
    project = ProjectDef(
        dirs=[
            ProjectDir(id="test/dummy_projects/test_requirements", kind="uv-pip-embed")
        ]
    )

    versions = ["3.10", "3.11", "3.12", "3.13"]
    results = []

    for version in versions:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Testing Python {version}")
        logger.info(f"{'=' * 60}")

        try:
            # Generate schematics for this Python version
            schematics = await schematics_universal(
                target=project, python_version=version
            )

            builder = schematics.builder
            assert builder is not None

            logger.info(f"✓ Successfully created schematic for Python {version}")
            logger.info(f"  Base image: {builder.base_image}")

            # Get entrypoint script
            entrypoint_script = await builder.a_entrypoint_script()

            # Check for UV commands
            scripts_str = " ".join(builder.scripts)
            assert "uv" in scripts_str.lower() or "UV" in scripts_str, (
                f"UV not found in scripts for Python {version}"
            )
            assert "pip" in scripts_str, (
                f"pip not found in scripts for Python {version}"
            )

            # Check for requirements.txt
            all_content = scripts_str + " " + entrypoint_script
            assert "requirements.txt" in all_content, (
                f"requirements.txt not found for Python {version}"
            )

            results.append(
                {
                    "version": version,
                    "status": "✓ PASSED",
                    "base_image": builder.base_image,
                    "has_uv": "uv" in scripts_str.lower() or "UV" in scripts_str,
                    "has_requirements": "requirements.txt" in all_content,
                }
            )

        except Exception as e:
            logger.error(f"✗ Failed for Python {version}: {e!s}")
            results.append({"version": version, "status": "✗ FAILED", "error": str(e)})

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("PYTHON VERSION TEST SUMMARY (requirements.txt)")
    logger.info(f"{'=' * 60}")

    for result in results:
        if "error" in result:
            logger.info(f"Python {result['version']:4} {result['status']}")
        else:
            logger.info(
                f"Python {result['version']:4} {result['status']} - {result['base_image']}"
            )

    passed = sum(1 for r in results if "PASSED" in r["status"])
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} passed")

    # Assert all tests passed
    assert passed == total, f"Only {passed}/{total} Python version tests passed"


# Test 5: Test Python versions 3.10-3.13 with setup.py
@injected_pytest(_design)
async def test_uv_pip_embed_python_versions_setuppy(schematics_universal, logger):
    """Test uv-pip-embed with Python 3.10-3.13 for setup.py project"""
    logger.info("Testing uv-pip-embed with Python 3.10-3.13 (setup.py)")

    # Create project
    project = ProjectDef(
        dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="uv-pip-embed")]
    )

    versions = ["3.10", "3.11", "3.12", "3.13"]
    results = []

    for version in versions:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Testing Python {version}")
        logger.info(f"{'=' * 60}")

        try:
            # Generate schematics for this Python version
            schematics = await schematics_universal(
                target=project, python_version=version
            )

            builder = schematics.builder
            assert builder is not None

            logger.info(f"✓ Successfully created schematic for Python {version}")
            logger.info(f"  Base image: {builder.base_image}")

            # Get entrypoint script
            entrypoint_script = await builder.a_entrypoint_script()

            # Check for UV commands
            scripts_str = " ".join(builder.scripts)
            assert "uv" in scripts_str.lower() or "UV" in scripts_str, (
                f"UV not found in scripts for Python {version}"
            )
            assert "pip" in scripts_str, (
                f"pip not found in scripts for Python {version}"
            )

            # Check for setup.py
            all_content = scripts_str + " " + entrypoint_script
            assert "setup.py" in all_content or "pip install -e" in all_content, (
                f"setup.py installation not found for Python {version}"
            )

            results.append(
                {
                    "version": version,
                    "status": "✓ PASSED",
                    "base_image": builder.base_image,
                    "has_uv": "uv" in scripts_str.lower() or "UV" in scripts_str,
                    "has_setup": "setup.py" in all_content
                    or "pip install -e" in all_content,
                }
            )

        except Exception as e:
            logger.error(f"✗ Failed for Python {version}: {e!s}")
            results.append({"version": version, "status": "✗ FAILED", "error": str(e)})

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("PYTHON VERSION TEST SUMMARY (setup.py)")
    logger.info(f"{'=' * 60}")

    for result in results:
        if "error" in result:
            logger.info(f"Python {result['version']:4} {result['status']}")
        else:
            logger.info(
                f"Python {result['version']:4} {result['status']} - {result['base_image']}"
            )

    passed = sum(1 for r in results if "PASSED" in r["status"])
    total = len(results)
    logger.info(f"\nTotal: {passed}/{total} passed")

    # Assert all tests passed
    assert passed == total, f"Only {passed}/{total} Python version tests passed"
