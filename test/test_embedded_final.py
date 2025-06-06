"""Simple IProxy-based test for embedded components"""

from pathlib import Path
from pinjected import *
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
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
    }
)

# Test design - use zeus for Docker host and context
test_design = design(
    storage_resolver=test_storage_resolver,
    logger=logger,
    docker_host="zeus",
    ml_nexus_docker_build_context="zeus",  # Use zeus build context
    ml_nexus_default_base_image="python:3.11-slim",
)

__meta_design__ = design(overrides=load_env_design + test_design)

# Test 1: UV auto-embed
test_uv_project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
test_uv_schematic: IProxy = schematics_universal(target=test_uv_project)
test_uv_docker = injected(DockerEnvFromSchematics)(
    project=test_uv_project, schematics=test_uv_schematic, docker_host="zeus"
)
test_uv_run: IProxy = test_uv_docker.run_script("""
echo "=== UV Auto-Embed Test ==="
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'✓ requests {requests.__version__}')"
python -c "import pydantic; print(f'✓ pydantic {pydantic.__version__}')"
echo "Running main.py:"
cd /sources/test_uv && python main.py
""")

# Test 2: Pyvenv-embed
test_pyvenv_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
)
test_pyvenv_schematic: IProxy = schematics_universal(
    target=test_pyvenv_project, python_version="3.11"
)
test_pyvenv_docker = injected(DockerEnvFromSchematics)(
    project=test_pyvenv_project, schematics=test_pyvenv_schematic, docker_host="zeus"
)
test_pyvenv_run: IProxy = test_pyvenv_docker.run_script("""
echo "=== Pyvenv-Embed Test ==="
echo "Python version:"
python --version
echo "Testing imports:"
python -c "import requests; print(f'✓ requests {requests.__version__}')"
python -c "import pandas; print(f'✓ pandas {pandas.__version__}')"
python -c "import numpy; print(f'✓ numpy {numpy.__version__}')"
python -c "import flask; print(f'✓ flask {flask.__version__}')"
""")
