from pinjected import *

from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.testing.test_resources import test_project
from ml_nexus.project_structure import ProjectDef
from ml_nexus.schematics import ContainerSchematic


@injected
async def a_macro_install_uv():
    return [
        "RUN curl -LsSf https://astral.sh/uv/install.sh | sh",
        'SHELL ["/bin/bash", "-lc"]',
        'RUN echo "source $HOME/.cargo/env" >> $HOME/.bashrc',
        "RUN cat $HOME/.bashrc",
        "RUN uv --version",
    ]


@injected
async def schematics_with_uv(  # noqa: PINJ006
    a_build_schematics_from_component,
    a_uv_component,
    a_hf_cache_component,
    a_gather_mount_request_for_project,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu20.04",
) -> ContainerSchematic:
    """
    Build container schematics for uv projects using the component system.
    This ensures git safe directory is configured via base_apt_packages_component.
    """
    assert target.dirs[0].kind in ["uv"], (
        f"the first dir of the project must be uv. got {target.dirs[0].kind},{target.dirs[0].id}"
    )

    # Use component system which includes git safe directory via base_apt_packages_component
    uv_comp = await a_uv_component(target=target)
    hf_cache_comp = await a_hf_cache_component()

    schematic = await a_build_schematics_from_component(
        base_image=base_image, components=[uv_comp, hf_cache_comp]
    )

    # Add dynamic mounts
    dynamic_mounts = await a_gather_mount_request_for_project(target)
    schematic.mount_requests.extend(dynamic_mounts)

    return schematic


project = test_project
uv_schem: IProxy = schematics_with_uv(target=project)
uv_docker = injected(DockerEnvFromSchematics)(
    project=project,
    schematics=uv_schem,
    docker_host=injected("ml_nexus_test_docker_host"),
)

run_test: IProxy = uv_docker.run_script("uv --version")
run_test_cache: IProxy = uv_docker.run_script("""
uv run python -c 'print("hello")'
""")

__meta_design__ = design(overrides=load_env_design)
