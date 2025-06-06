"""Simple test to verify embedded components have no cache mounts"""

import asyncio
from pathlib import Path
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from pinjected import design
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
)


async def test_pyenv_embedded_no_mounts():
    """Test that pyenv embedded component has no mounts"""
    from pinjected import injected

    @injected
    async def check_mounts(
        a_pyenv_component_embedded,
        /,
    ):
        project = ProjectDef(
            dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
        )
        component = await a_pyenv_component_embedded(
            target=project, python_version="3.11"
        )
        return component

    # Run with design
    from pinjected.run_helpers import run_async_injected

    component = await run_async_injected(check_mounts, overrides=test_design)

    # Check mounts
    print(f"Pyenv embedded mounts: {component.mounts}")
    assert component.mounts == [], f"Expected no mounts, but got: {component.mounts}"
    print("✅ Pyenv embedded has no cache mounts")


async def test_uv_embedded_no_mounts():
    """Test that UV embedded component has no mounts"""
    from pinjected import injected

    @injected
    async def check_mounts(
        a_uv_component_embedded,
        /,
    ):
        project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv-embedded")])
        component = await a_uv_component_embedded(target=project)
        return component

    # Run with design
    from pinjected.run_helpers import run_async_injected

    component = await run_async_injected(check_mounts, overrides=test_design)

    # Check mounts
    print(f"UV embedded mounts: {component.mounts}")
    assert component.mounts == [], f"Expected no mounts, but got: {component.mounts}"
    print("✅ UV embedded has no cache mounts")


async def test_requirements_txt_embedded_no_mounts():
    """Test that requirements.txt embedded component has no mounts"""
    from pinjected import injected

    @injected
    async def check_mounts(
        a_component_to_install_requirements_txt_embedded,
        /,
    ):
        project = ProjectDef(
            dirs=[ProjectDir("test_requirements", kind="requirements-embedded")]
        )
        component = await a_component_to_install_requirements_txt_embedded(
            target=project
        )
        return component

    # Run with design
    from pinjected.run_helpers import run_async_injected

    component = await run_async_injected(check_mounts, overrides=test_design)

    # Check mounts
    print(f"Requirements.txt embedded mounts: {component.mounts}")
    assert component.mounts == [], f"Expected no mounts, but got: {component.mounts}"
    print("✅ Requirements.txt embedded has no cache mounts")


async def main():
    """Run all tests"""
    print("Testing embedded components have no cache mounts...")
    print("-" * 60)

    try:
        await test_pyenv_embedded_no_mounts()
    except Exception as e:
        print(f"❌ Pyenv embedded test failed: {e}")

    print()

    try:
        await test_uv_embedded_no_mounts()
    except Exception as e:
        print(f"❌ UV embedded test failed: {e}")

    print()

    try:
        await test_requirements_txt_embedded_no_mounts()
    except Exception as e:
        print(f"❌ Requirements.txt embedded test failed: {e}")

    print("-" * 60)
    print("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
