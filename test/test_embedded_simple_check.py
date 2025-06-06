"""Direct test of embedded components mount configuration"""

from pathlib import Path
from pinjected import *
from ml_nexus.schematics_util.universal import (
    a_pyenv_component_embedded,
    a_uv_component_embedded,
    a_component_to_install_requirements_txt_embedded,
)
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
)

# Create test IProxies
test_pyenv_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
)
test_pyenv_embedded_component: IProxy = a_pyenv_component_embedded(
    target=test_pyenv_project, python_version="3.11"
)
test_pyenv_mounts: IProxy = test_pyenv_embedded_component.mounts

test_uv_project = ProjectDef(dirs=[ProjectDir("test_uv", kind="uv-embedded")])
test_uv_embedded_component: IProxy = a_uv_component_embedded(target=test_uv_project)
test_uv_mounts: IProxy = test_uv_embedded_component.mounts

test_req_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="requirements-embedded")]
)
test_req_embedded_component: IProxy = a_component_to_install_requirements_txt_embedded(
    target=test_req_project
)
test_req_mounts: IProxy = test_req_embedded_component.mounts

# Design for testing
__meta_design__ = design(overrides=test_design)
