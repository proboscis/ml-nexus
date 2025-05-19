from pathlib import Path

from pinjected import *

from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.testing.test_resources import test_project
from ml_nexus.project_structure import ProjectDef
from ml_nexus.schematics import CacheMountRequest, ContainerSchematic


@injected
async def a_macro_install_uv():
    return [
        "RUN curl -LsSf https://astral.sh/uv/install.sh | sh",
        'SHELL ["/bin/bash", "-lc"]',
        'RUN echo "source $HOME/.cargo/env" >> $HOME/.bashrc',
        'RUN cat $HOME/.bashrc',
        'RUN uv --version',
    ]


@injected
async def schematics_with_uv(
        new_DockerBuilder,
        a_macro_install_uv,
        a_gather_mount_request_for_project,
        /,
        target: ProjectDef,
        base_image='nvidia/cuda:12.3.1-devel-ubuntu20.04',
) -> ContainerSchematic:
    hf_cache_mount = Path("/cache/huggingface")
    proj_dir = target.default_working_dir
    assert target.dirs[0].kind in ['uv'], f"the first dir of the project must be uv. got {target.dirs[0].kind},{target.dirs[0].id}"
    builder = new_DockerBuilder(
        base_image=base_image,
        macros=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl git clang rsync",
            await a_macro_install_uv(),
            f'ENV HF_HOME={hf_cache_mount}',
            f'WORKDIR {target.default_working_dir}'
        ],
        scripts=[
            f"cd {proj_dir}", # WORKDIR has no effect on K8S, so we set it here.
            "source $HOME/.cargo/env",
            "uv sync",
            f"source {proj_dir / '.venv/bin/activate'}"
        ]
    )
    dynamic_mounts = await a_gather_mount_request_for_project(target)
    cache_mounts = [
        CacheMountRequest(
            'uv_cache', Path('/root/.cache/uv')
        ),
        CacheMountRequest(
            'hf_cache', hf_cache_mount
        ),
    ]
    return ContainerSchematic(
        builder=builder,
        mount_requests=[
            *dynamic_mounts,
            *cache_mounts
        ]
    )


project = test_project
uv_schem: IProxy = schematics_with_uv(
    target=project
)
uv_docker = injected(DockerEnvFromSchematics)(
    project=project,
    schematics=uv_schem,
    docker_host=injected('ml_nexus_test_docker_host')
)

run_test: IProxy = uv_docker.run_script("uv --version")
run_test_cache: IProxy = uv_docker.run_script("""
uv run python -c 'print("hello")'
""")

__meta_design__ = design(
    overrides=load_env_design
)
