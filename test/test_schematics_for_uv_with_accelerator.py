"""Test UV project with CUDA accelerator using schematics

This test verifies that UV projects with CUDA dependencies can be properly
built and run using the schematics system.
"""

from pathlib import Path
import tempfile
from pinjected import design
from pinjected.test import injected_pytest
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.storage_resolver import StaticStorageResolver
from loguru import logger


# Create a test UV project with accelerator dependencies
def create_test_uv_accelerator_project():
    """Create a temporary UV project with CUDA dependencies"""
    tmpdir = Path(tempfile.mkdtemp())
    project_path = tmpdir / "uv_with_accelerator"
    project_path.mkdir()
    
    # Create pyproject.toml with CUDA dependencies
    pyproject_content = """[project]
name = "test-accelerator"
version = "0.1.0"
dependencies = []

[project.optional-dependencies]
build = ["torch>=2.0.0"]
basicsr = ["basicsr>=1.4.0"]

[tool.uv]
dev-dependencies = []
"""
    (project_path / "pyproject.toml").write_text(pyproject_content)
    
    # Create a simple Python file
    (project_path / "main.py").write_text("""
import sys
print(f"Python {sys.version}")
try:
    import torch
    print(f"PyTorch {torch.__version__}")
except ImportError:
    print("PyTorch not installed")
""")
    
    return project_path


# Set up test project at module level
test_project_path = create_test_uv_accelerator_project()
test_storage_resolver = StaticStorageResolver({
    "uv_with_accelerator": test_project_path
})

project_uv_with_accelerator = ProjectDef(
    dirs=[ProjectDir(id="uv_with_accelerator", kind="uv", excludes=[".venv", ".git"])]
)



# Test design configuration
test_design = load_env_design + design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    docker_host="localhost",  # Use local Docker for testing
    ml_nexus_docker_build_context="default",  # Use default Docker context
)


# ===== Test 1: Basic schematic generation test =====
@injected_pytest(test_design)
async def test_uv_accelerator_schematic_generation(schematics_universal, logger):
    """Test generating schematics for UV project with CUDA dependencies"""
    logger.info("Testing UV accelerator schematic generation")

    # Generate schematics
    schematic = await schematics_universal(
        target=project_uv_with_accelerator,
        base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
        python_version="3.10"
    )

    # Verify schematic is generated
    assert schematic is not None
    assert schematic.builder is not None
    assert schematic.builder.base_image == "nvidia/cuda:12.3.1-devel-ubuntu22.04"
    
    # Check that UV commands are present
    scripts_str = " ".join(schematic.builder.scripts)
    assert "uv" in scripts_str.lower() or "UV" in scripts_str
    
    logger.info("✅ Schematic generation test passed")


# ===== Test 2: Hacked schematics with extra dependencies =====
@injected_pytest(test_design)
async def test_hacked_schematics_with_extras(schematics_universal, logger):
    """Test applying script transformation for extra dependencies"""
    logger.info("Testing hacked schematics with extra dependencies")

    # Generate base schematics
    base_schematic = await schematics_universal(
        target=project_uv_with_accelerator,
        base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
        python_version="3.10"
    )
    
    # Apply the hack to replace uv sync with extra dependencies
    hacked_scripts = []
    for script in base_schematic.builder.scripts:
        if "uv sync" in script:
            hacked_scripts.extend(["uv sync --extra build", "uv sync --extra build --extra basicsr"])
        else:
            hacked_scripts.append(script)
    
    # Verify the hack was applied
    scripts_str = " ".join(hacked_scripts)
    assert "--extra build" in scripts_str
    assert "--extra basicsr" in scripts_str
    
    logger.info("✅ Hacked schematics test passed")


# ===== Test 3: Storage resolver =====
@injected_pytest(test_design)
async def test_storage_resolver(storage_resolver, logger):
    """Test that storage resolver is properly injected"""
    logger.info("Testing storage resolver injection")

    assert storage_resolver is not None
    assert hasattr(storage_resolver, 'locate')
    
    # Test that our test project can be resolved
    resolved_path = await storage_resolver.locate("uv_with_accelerator")
    assert resolved_path is not None
    assert resolved_path.exists()
    
    logger.info("✅ Storage resolver test passed")
