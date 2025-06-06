"""Direct test of embedded components Docker execution"""

import asyncio
import sys
from pathlib import Path
from pinjected import injected, Injected
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from ml_nexus import load_env_design
from pinjected import design
from loguru import logger

# Create storage resolver for test projects
TEST_PROJECT_ROOT = Path(__file__).parent / "dummy_projects"

test_storage_resolver = StaticStorageResolver(
    {
        "test_uv": TEST_PROJECT_ROOT / "test_uv",
        "test_requirements": TEST_PROJECT_ROOT / "test_requirements",
    }
)

# Configure design
__design__ = load_env_design + design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    docker_host="local",
    ml_nexus_default_base_image="python:3.11-slim",
)


@injected
async def test_embedded_execution():
    """Test embedded Docker execution"""
    print("=" * 60)
    print("Testing Embedded Components Docker Execution")
    print("=" * 60)

    # Test 1: UV auto-embed
    print("\n1. Testing UV auto-embed...")
    try:
        project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
        schematic = await Injected.a_call(schematics_universal, target=project)

        # Check mounts
        cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
        print(f"Cache mounts: {[m.cache_name for m in cache_mounts]}")

        # Create Docker env
        docker_env = Injected.call(
            DockerEnvFromSchematics,
            project=project,
            schematics=schematic,
            docker_host="local",
        )

        # Run test
        print("Building and running container...")
        result = await docker_env.run_script("""
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'requests: {requests.__version__}')" || echo "requests import failed"
python -c "import pydantic; print(f'pydantic: {pydantic.__version__}')" || echo "pydantic import failed"
        """)

        print(f"Exit code: {result.exit_code}")
        print(f"Output:\n{result.stdout}")
        if result.stderr:
            print(f"Errors:\n{result.stderr}")

        if result.exit_code == 0 and "requests:" in result.stdout:
            print("✅ UV auto-embed test PASSED")
        else:
            print("❌ UV auto-embed test FAILED")

    except Exception as e:
        print(f"❌ UV auto-embed test ERROR: {e}")
        import traceback

        traceback.print_exc()

    print("-" * 60)

    # Test 2: Pyvenv-embed with requirements.txt
    print("\n2. Testing pyvenv-embed with requirements.txt...")
    try:
        project = ProjectDef(
            dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
        )
        schematic = await Injected.a_call(
            schematics_universal, target=project, python_version="3.11"
        )

        # Check mounts
        cache_mounts = [m for m in schematic.mount_requests if hasattr(m, "cache_name")]
        print(f"Cache mounts: {[m.cache_name for m in cache_mounts]}")

        # Create Docker env
        docker_env = Injected.call(
            DockerEnvFromSchematics,
            project=project,
            schematics=schematic,
            docker_host="local",
        )

        # Run test
        print("Building and running container...")
        result = await docker_env.run_script("""
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'requests: {requests.__version__}')" || echo "requests import failed"
python -c "import pandas; print(f'pandas: {pandas.__version__}')" || echo "pandas import failed"
python -c "import numpy; print(f'numpy: {numpy.__version__}')" || echo "numpy import failed"
        """)

        print(f"Exit code: {result.exit_code}")
        print(f"Output:\n{result.stdout}")
        if result.stderr:
            print(f"Errors:\n{result.stderr}")

        if result.exit_code == 0 and all(
            pkg in result.stdout for pkg in ["requests:", "pandas:", "numpy:"]
        ):
            print("✅ Pyvenv-embed test PASSED")
        else:
            print("❌ Pyvenv-embed test FAILED")

    except Exception as e:
        print(f"❌ Pyvenv-embed test ERROR: {e}")
        import traceback

        traceback.print_exc()

    print("=" * 60)
    print("Tests completed!")


if __name__ == "__main__":
    try:
        # Run the injected function properly
        import asyncio
        from pinjected import Injected

        async def main():
            await Injected.a_call(test_embedded_execution)

        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted!")
        sys.exit(1)
