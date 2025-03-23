from pathlib import Path

from pinjected.test import injected_pytest
from pinjected import injected
from pinjected.test.injected_pytest import _to_pytest

from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics, DockerHostPlacement
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import ContainerSchematic
from ml_nexus.schematics_util.universal import SchematicsUniversal, schematics_universal
from pinjected import design, IProxy
from ml_nexus.storage_resolver import DirectoryStorageResolver, IdPath
from ml_nexus import load_env_design
from loguru import logger


def to_pytest(tgt):
    return _to_pytest(tgt, design(), __file__)


project_uv_with_accelerator = ProjectDef(
    dirs=[
        ProjectDir(
            id='uv_with_accelerator',
            kind='uv',
            excludes=[
                ".venv", ".git"
            ]
        )
    ]
)
schematics_uv_with_accelerator: IProxy[ContainerSchematic] = schematics_universal(
    project_uv_with_accelerator,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    python_version='3.10'
)


# A hack is:
# replace uv sync with other lines.
@injected
async def a_hack_uv_sync_with_torch_dep_package(lines: list[str]) -> list[str]:
    # This hack works!
    res = []
    for line in lines:
        if 'uv sync' in line:
            res += [
                "uv sync --extra build",
                "uv sync --extra build --extra basicsr"
            ]
        else:
            res.append(line)
    return res


hacked_schematics = schematics_uv_with_accelerator.a_map_scripts(a_hack_uv_sync_with_torch_dep_package).await__()

remote_docker_env = injected(DockerEnvFromSchematics)(
    project=project_uv_with_accelerator,
    schematics=hacked_schematics,
    docker_host='zeus',
    placement=DockerHostPlacement(
        cache_root=Path('/tmp/cache_root'),
        resource_root=Path('/tmp/resource_root'),
        source_root=Path('/tmp/source_root'),
        direct_root=Path('/tmp/direct_root')
    )
)
run_script_zeus: IProxy = remote_docker_env.run_script('echo "Hello, World!"')
local_docker_env = injected(DockerEnvFromSchematics)(
    project=project_uv_with_accelerator,
    schematics=hacked_schematics,
    docker_host='localhost',
    placement=DockerHostPlacement(
        cache_root=Path('/tmp/cache_root'),
        resource_root=Path('/tmp/resource_root'),
        source_root=Path('/tmp/source_root'),
        direct_root=Path('/tmp/direct_root')
    )
)
run_python_zeus:IProxy = remote_docker_env.run_script('python -c "import torch; import basicsr; print(torch.__version__)"')

test_run_script = to_pytest(run_script_zeus)

test_storage_resolver = to_pytest(injected("storage_resolver"))

__meta_design__ = design(
    overrides=load_env_design + design(
        storage_resolver=DirectoryStorageResolver(
            Path("~/repos/ml-nexus-test-repositories").expanduser(),
        ),
        logger=logger,
    )
)

if __name__ == '__main__':
    pass
