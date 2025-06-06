"""Test iproxy objects for different ProjectDir kinds in schematics_universal"""

from pinjected import *
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal

# Test case for 'source' kind - no Python environment setup needed
test_schematics_source: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_source_project", kind="source")]),
    base_image="ubuntu:22.04",
)

# Test case for 'resource' kind - resource files only
test_schematics_resource: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_resource_data", kind="resource")]),
    base_image="ubuntu:22.04",
)

# Test case for 'auto' kind - auto-detect based on project files
test_schematics_auto: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_auto_project", kind="auto")]),
    base_image="python:3.11-slim",
)

# Test case for 'rye' kind - Rye project management
test_schematics_rye: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_rye_project", kind="rye")]),
    base_image="python:3.11-slim",
)

# Test case for 'uv' kind - UV project management
test_schematics_uv: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_uv_project", kind="uv")]),
    base_image="python:3.11-slim",
)

# Test case for 'setup.py' kind - setup.py based project
test_schematics_setup_py: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_setuppy_project", kind="setup.py")]),
    base_image="python:3.11-slim",
)

# Test case with multiple directories of different kinds
test_schematics_mixed: IProxy = schematics_universal(
    target=ProjectDef(
        dirs=[
            ProjectDir("main_source", kind="uv"),
            ProjectDir("data_resources", kind="resource", dependencies=[]),
            ProjectDir("utils_lib", kind="source", dependencies=[]),
        ]
    ),
    base_image="python:3.11-slim",
)

# Test case with custom python version
test_schematics_custom_python: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_py310_project", kind="uv")]),
    base_image="python:3.10-slim",
    python_version="3.10",
)

# Test case for requirements.txt (detected via auto)
test_schematics_requirements: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_requirements_project", kind="auto")]),
    # This should auto-detect requirements.txt if present
    base_image="python:3.11-slim",
)

# Test case with nvidia/cuda base image for GPU support
test_schematics_gpu: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("test_gpu_project", kind="uv")]),
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
)

# Design override for testing
__meta_design__ = design(
    # Add any necessary overrides for testing
)
