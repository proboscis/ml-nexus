"""Runner to test different ProjectDir kinds with schematics_universal"""

from pathlib import Path
from pinjected import *
from ml_nexus import load_env_design
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics_util.universal import schematics_universal
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics

# Test runners for each kind

# 1. Source kind test - no Python environment
test_source_project = ProjectDef(
    dirs=[ProjectDir('ml_nexus', kind='source')]  # Using current project as test
)
test_source_schematics: IProxy = schematics_universal(
    target=test_source_project,
    base_image='ubuntu:22.04'
)
test_source_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_source_project,
    schematics=test_source_schematics,
    docker_host='local'
)
test_source_run: IProxy = test_source_env.run_script("""
echo "Testing source kind - no Python environment"
ls -la
pwd
""")

# 2. Resource kind test
test_resource_project = ProjectDef(
    dirs=[ProjectDir('doc', kind='resource')]  # Using doc folder as resource
)
test_resource_schematics: IProxy = schematics_universal(
    target=test_resource_project,
    base_image='ubuntu:22.04'
)
test_resource_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_resource_project,
    schematics=test_resource_schematics,
    docker_host='local'
)
test_resource_run: IProxy = test_resource_env.run_script("""
echo "Testing resource kind"
ls -la /resources/
""")

# 3. Auto kind test - will auto-detect project type
test_auto_project = ProjectDef(
    dirs=[ProjectDir('ml_nexus', kind='auto')]
)
test_auto_schematics: IProxy = schematics_universal(
    target=test_auto_project,
    base_image='python:3.11-slim'
)
test_auto_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_auto_project,
    schematics=test_auto_schematics,
    docker_host='local'
)
test_auto_run: IProxy = test_auto_env.run_script("""
echo "Testing auto kind - should detect UV project"
which python
python --version
""")

# 4. UV kind test
test_uv_project = ProjectDef(
    dirs=[ProjectDir('ml_nexus', kind='uv')]
)
test_uv_schematics: IProxy = schematics_universal(
    target=test_uv_project,
    base_image='python:3.11-slim'
)
test_uv_env: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_uv_project,
    schematics=test_uv_schematics,
    docker_host='local',
    container_name='test_uv_kind'
)
test_uv_run: IProxy = test_uv_env.run_script("""
echo "Testing UV kind"
which uv
uv --version
python --version
uv pip list | head -10
""")

# 5. Rye kind test (using a mock project)
test_rye_project = ProjectDef(
    dirs=[ProjectDir('test_rye_mock', kind='rye')]
)
test_rye_schematics: IProxy = schematics_universal(
    target=test_rye_project,
    base_image='python:3.11-slim'
)
test_rye_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_rye_project,
    schematics=test_rye_schematics,
    docker_host='local'
)
test_rye_run: IProxy = test_rye_env.run_script("""
echo "Testing Rye kind"
which rye
rye --version
""")

# 6. Setup.py kind test
test_setuppy_project = ProjectDef(
    dirs=[ProjectDir('test_setuppy_mock', kind='setup.py')]
)
test_setuppy_schematics: IProxy = schematics_universal(
    target=test_setuppy_project,
    base_image='python:3.11-slim',
    python_version='3.11'
)
test_setuppy_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_setuppy_project,
    schematics=test_setuppy_schematics,
    docker_host='local'
)
test_setuppy_run: IProxy = test_setuppy_env.run_script("""
echo "Testing setup.py kind"
python --version
pip --version
""")

# 7. Mixed kinds test
test_mixed_project = ProjectDef(
    dirs=[
        ProjectDir('ml_nexus', kind='uv'),
        ProjectDir('doc', kind='resource'),
    ]
)
test_mixed_schematics: IProxy = schematics_universal(
    target=test_mixed_project,
    base_image='python:3.11-slim'
)
test_mixed_env: IProxy = injected(DockerEnvFromSchematics)(
    project=test_mixed_project,
    schematics=test_mixed_schematics,
    docker_host='local'
)
test_mixed_run: IProxy = test_mixed_env.run_script("""
echo "Testing mixed kinds"
ls -la /sources/
ls -la /resources/
python --version
""")

# Test with GPU base image
test_gpu_project = ProjectDef(
    dirs=[ProjectDir('ml_nexus', kind='uv')]
)
test_gpu_schematics: IProxy = schematics_universal(
    target=test_gpu_project,
    base_image='nvidia/cuda:12.3.1-devel-ubuntu22.04',
    python_version='3.11'
)

# Design configuration
__meta_design__ = design(
    overrides=load_env_design + design(
        docker_host='local'  # Override to use local docker
    )
)