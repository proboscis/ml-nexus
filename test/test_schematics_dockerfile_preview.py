"""Preview Dockerfiles generated for different ProjectDir kinds"""

from pathlib import Path
from pinjected import *
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from loguru import logger

# Test to preview generated Dockerfiles for each kind

# 1. Source kind - should have minimal setup
test_source_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('test_source', kind='source')]),
    base_image='ubuntu:22.04'
).builder.dockerfile

# 2. Resource kind - should mount resources
test_resource_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('test_resource', kind='resource')]),
    base_image='ubuntu:22.04'
).builder.dockerfile

# 3. UV kind - should install UV and sync
test_uv_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('test_uv', kind='uv')]),
    base_image='python:3.11-slim'
).builder.dockerfile

# 4. Rye kind - should install Rye and sync
test_rye_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('test_rye', kind='rye')]),
    base_image='python:3.11-slim'
).builder.dockerfile

# 5. Setup.py kind - should use pyenv and pip install -e .
test_setuppy_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('test_setuppy', kind='setup.py')]),
    base_image='python:3.11-slim',
    python_version='3.11'
).builder.dockerfile

# 6. Auto kind with requirements.txt detection
test_requirements_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('sketch2lineart', kind='auto')]),  # This project has requirements.txt
    base_image='python:3.11-slim'
).builder.dockerfile

# 7. Mixed project with multiple kinds
test_mixed_dockerfile: IProxy = schematics_universal(
    target=ProjectDef(dirs=[
        ProjectDir('main_app', kind='uv'),
        ProjectDir('data', kind='resource'),
        ProjectDir('scripts', kind='source')
    ]),
    base_image='python:3.11-slim'
).builder.dockerfile

# Function to print dockerfile with header
@injected
async def a_print_dockerfile(name: str, dockerfile: str):
    logger.info(f"\n{'='*60}")
    logger.info(f"Dockerfile for {name}")
    logger.info(f"{'='*60}")
    logger.info(f"\n{dockerfile}\n")
    return dockerfile

# Test runners that print dockerfiles
test_print_source: IProxy = a_print_dockerfile("SOURCE kind", test_source_dockerfile)
test_print_resource: IProxy = a_print_dockerfile("RESOURCE kind", test_resource_dockerfile)
test_print_uv: IProxy = a_print_dockerfile("UV kind", test_uv_dockerfile)
test_print_rye: IProxy = a_print_dockerfile("RYE kind", test_rye_dockerfile)
test_print_setuppy: IProxy = a_print_dockerfile("SETUP.PY kind", test_setuppy_dockerfile)
test_print_requirements: IProxy = a_print_dockerfile("AUTO kind (requirements.txt)", test_requirements_dockerfile)
test_print_mixed: IProxy = a_print_dockerfile("MIXED kinds", test_mixed_dockerfile)

# Run all previews
test_print_all: IProxy = injected.list(
    test_print_source,
    test_print_resource,
    test_print_uv,
    test_print_rye,
    test_print_setuppy,
    test_print_requirements,
    test_print_mixed
)

# Design configuration
__meta_design__ = design(
    overrides=load_env_design
)