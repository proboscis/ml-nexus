"""Test embedded components by actually running Python scripts in Docker containers"""

from pathlib import Path
from pinjected import *
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics
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
    docker_host="local",  # Use local Docker
)

# Test 1: Auto-embed UV project
test_uv_project = ProjectDef(dirs=[ProjectDir("test_uv", kind="auto-embed")])
test_uv_schematic: IProxy = schematics_universal(target=test_uv_project)
test_uv_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_uv_project,
    schematics=test_uv_schematic,
    docker_host="local",
    container_name="test_embed_uv",
)

# Run Python script to verify UV dependencies
test_uv_run: IProxy = test_uv_docker.run_script("""
echo "=== Testing UV auto-embed project ==="
python --version
echo "--- Checking UV installation ---"
which uv || echo "UV not found"
uv --version || echo "UV command failed"
echo "--- Testing Python imports ---"
python -c "
import sys
print(f'Python path: {sys.executable}')
print('Testing embedded dependencies:')
try:
    import requests
    print(f'✓ requests {requests.__version__}')
except ImportError as e:
    print(f'✗ requests import failed: {e}')
try:
    import pydantic
    print(f'✓ pydantic {pydantic.__version__}')
except ImportError as e:
    print(f'✗ pydantic import failed: {e}')
"
echo "--- Running project main.py ---"
cd /sources/test_uv
python main.py || echo "main.py execution failed"
""")

# Test 2: Pyvenv-embed with requirements.txt
test_pyvenv_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="pyvenv-embed")]
)
test_pyvenv_schematic: IProxy = schematics_universal(
    target=test_pyvenv_project, python_version="3.11"
)
test_pyvenv_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_pyvenv_project,
    schematics=test_pyvenv_schematic,
    docker_host="local",
    container_name="test_embed_pyvenv",
)

# Run Python script to verify pyenv dependencies
test_pyvenv_run: IProxy = test_pyvenv_docker.run_script("""
echo "=== Testing pyvenv-embed project ==="
python --version
which python
echo "--- Testing Python imports from requirements.txt ---"
python -c "
import sys
print(f'Python path: {sys.executable}')
print('Testing embedded dependencies:')
deps = [
    ('requests', '2.31.0'),
    ('pandas', '2.1.4'),
    ('numpy', '1.26.2'),
    ('flask', '3.0.0'),
    ('pytest', '7.4.3')
]
for pkg, expected_ver in deps:
    try:
        mod = __import__(pkg)
        version = getattr(mod, '__version__', 'unknown')
        print(f'✓ {pkg} {version} (expected {expected_ver})')
    except ImportError as e:
        print(f'✗ {pkg} import failed: {e}')
"
echo "--- Running app.py ---"
cd /sources/test_requirements
python app.py || echo "app.py execution failed"
""")

# Test 3: Auto-embed with requirements.txt
test_req_auto_project = ProjectDef(
    dirs=[ProjectDir("test_requirements", kind="auto-embed")]
)
test_req_auto_schematic: IProxy = schematics_universal(target=test_req_auto_project)
test_req_auto_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_req_auto_project,
    schematics=test_req_auto_schematic,
    docker_host="local",
    container_name="test_embed_req_auto",
)

# Run Python script to verify auto-detected requirements.txt
test_req_auto_run: IProxy = test_req_auto_docker.run_script("""
echo "=== Testing auto-embed requirements.txt project ==="
python --version
pip --version
echo "--- Listing installed packages ---"
pip list | grep -E "(requests|pandas|numpy|flask|pytest)" || echo "Expected packages not found"
echo "--- Testing imports ---"
python -c "
import requests, pandas, numpy, flask, pytest
print('✓ All imports successful')
print(f'requests: {requests.__version__}')
print(f'pandas: {pandas.__version__}')
print(f'numpy: {numpy.__version__}')
print(f'flask: {flask.__version__}')
print(f'pytest: {pytest.__version__}')
"
""")

# Test 4: Pyvenv-embed with setup.py
test_setuppy_project = ProjectDef(
    dirs=[ProjectDir("test_setuppy", kind="pyvenv-embed")]
)
test_setuppy_schematic: IProxy = schematics_universal(
    target=test_setuppy_project, python_version="3.11"
)
test_setuppy_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_setuppy_project,
    schematics=test_setuppy_schematic,
    docker_host="local",
    container_name="test_embed_setuppy",
)

# Run Python script to verify setup.py installation
test_setuppy_run: IProxy = test_setuppy_docker.run_script("""
echo "=== Testing pyvenv-embed with setup.py ==="
python --version
echo "--- Checking if package is installed ---"
pip list | grep test-setuppy || echo "test-setuppy package not found"
echo "--- Testing package import ---"
python -c "
try:
    import test_setuppy
    print('✓ test_setuppy package imported successfully')
    # Test that the package is properly installed
    import pkg_resources
    try:
        version = pkg_resources.get_distribution('test-setuppy').version
        print(f'✓ Package version: {version}')
    except:
        print('✗ Could not get package version')
except ImportError as e:
    print(f'✗ test_setuppy import failed: {e}')
"
""")

# Cleanup function to remove test containers
test_cleanup: IProxy = injected(
    lambda a_system, /: a_system(
        "docker rm -f test_embed_uv test_embed_pyvenv test_embed_req_auto test_embed_setuppy 2>/dev/null || true"
    )
)()

# Design for testing
__meta_design__ = design(overrides=test_design)
