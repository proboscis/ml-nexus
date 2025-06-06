"""Simpler test for embedded components with direct Docker execution"""

import asyncio
from pathlib import Path
from pinjected import injected, design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus import load_env_design
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
        "test_setuppy": TEST_PROJECT_ROOT / "test_setuppy",
    }
)

# Test design configuration
test_design = load_env_design + design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    ml_nexus_default_base_image="python:3.11-slim",
    docker_host="local",
)


@injected
async def test_uv_embedded(
    schematics_universal,
    new_DockerEnvFromSchematics,
    logger,
    /,
):
    """Test UV auto-embed project"""
    logger.info("Testing UV auto-embed project...")

    # Create project
    project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])

    # Generate schematics
    logger.info("Generating schematics...")
    schematic = await schematics_universal(target=project)

    # Check mounts
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    logger.info(f"Cache mounts: {cache_mounts}")

    # Create Docker environment
    logger.info("Creating Docker environment...")
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="local"
    )

    # Run simple test
    logger.info("Running Python test...")
    result = await docker_env.run_script("""
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'requests: {requests.__version__}')"
python -c "import pydantic; print(f'pydantic: {pydantic.__version__}')"
""")

    logger.info(f"Exit code: {result.exit_code}")
    logger.info(f"Stdout:\n{result.stdout}")
    if result.stderr:
        logger.error(f"Stderr:\n{result.stderr}")

    return result


@injected
async def test_pyvenv_embedded(
    schematics_universal,
    new_DockerEnvFromSchematics,
    logger,
    /,
):
    """Test pyvenv-embed with requirements.txt"""
    logger.info("Testing pyvenv-embed project...")

    # Create project
    project = ProjectDef(dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")])

    # Generate schematics
    logger.info("Generating schematics...")
    schematic = await schematics_universal(target=project, python_version="3.11")

    # Check mounts
    cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
    logger.info(f"Cache mounts: {cache_mounts}")

    # Create Docker environment
    logger.info("Creating Docker environment...")
    docker_env = new_DockerEnvFromSchematics(
        project=project, schematics=schematic, docker_host="local"
    )

    # Run simple test
    logger.info("Running Python test...")
    result = await docker_env.run_script("""
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'requests: {requests.__version__}')"
python -c "import pandas; print(f'pandas: {pandas.__version__}')"
python -c "import numpy; print(f'numpy: {numpy.__version__}')"
""")

    logger.info(f"Exit code: {result.exit_code}")
    logger.info(f"Stdout:\n{result.stdout}")
    if result.stderr:
        logger.error(f"Stderr:\n{result.stderr}")

    return result


async def main():
    """Run tests"""
    from pinjected.run_helpers import run_async_injected

    print("=" * 60)
    print("Testing Embedded Components Docker Execution")
    print("=" * 60)

    # Test UV embedded
    try:
        print("\n1. Testing UV auto-embed...")
        result = await run_async_injected(test_uv_embedded, overrides=test_design)
        if result.exit_code == 0:
            print("✅ UV auto-embed test PASSED")
        else:
            print("❌ UV auto-embed test FAILED")
    except Exception as e:
        print(f"❌ UV auto-embed test ERROR: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "-" * 60)

    # Test pyvenv embedded
    try:
        print("\n2. Testing pyvenv-embed...")
        result = await run_async_injected(test_pyvenv_embedded, overrides=test_design)
        if result.exit_code == 0:
            print("✅ Pyvenv-embed test PASSED")
        else:
            print("❌ Pyvenv-embed test FAILED")
    except Exception as e:
        print(f"❌ Pyvenv-embed test ERROR: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
