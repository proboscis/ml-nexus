"""Test to preview Dockerfile generation for embedded components"""

from pathlib import Path
from pinjected import *
from ml_nexus.schematics_util.universal import schematics_universal
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
)

# Create test schematics
test_auto_embed_uv_project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
test_auto_embed_uv_schematic: IProxy = schematics_universal(
    target=test_auto_embed_uv_project
)

test_pyvenv_embed_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
)
test_pyvenv_embed_schematic: IProxy = schematics_universal(
    target=test_pyvenv_embed_project, python_version="3.11"
)

# Extract Dockerfile content
test_auto_embed_uv_dockerfile: IProxy = (
    test_auto_embed_uv_schematic.builder.a_get_dockerfile_lines()
)
test_pyvenv_embed_dockerfile: IProxy = (
    test_pyvenv_embed_schematic.builder.a_get_dockerfile_lines()
)

# Check mount requests
test_auto_embed_uv_mounts: IProxy = test_auto_embed_uv_schematic.mount_requests
test_pyvenv_embed_mounts: IProxy = test_pyvenv_embed_schematic.mount_requests

# Design for testing
# __meta_design__ = design(overrides=test_design)  # Removed deprecated __meta_design__
