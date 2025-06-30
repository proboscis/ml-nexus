import asyncio
import base64
from contextlib import asynccontextmanager
from pathlib import Path

from beartype import beartype
from pinjected import *

from ml_nexus.docker.builder.builder_utils.rye_util import get_dummy_rye_venv
from ml_nexus.docker.builder.docker_builder import DockerBuilder
from ml_nexus.docker.builder.macros.macro_defs import BuildMacroContext, Macro, RCopy
from ml_nexus.project_structure import ProjectDef, ProjectDir, ProjectPlacement
from ml_nexus.schematics import (
    ResolveMountRequest,
    CacheMountRequest,
    ContainerSchematic,
    ContextualMountRequest,
    MountRequest,
)
from ml_nexus.storage_resolver import IStorageResolver
from ml_nexus.testing import ml_nexus_test_design


@injected
@beartype
async def build_entrypoint_script(scripts: list[str]):
    assert isinstance(scripts, list), (
        f"scripts must be a list of strings. got {type(scripts)}"
    )
    joined_script = "\n".join(scripts)
    entrypoint_script = f"""
#!/bin/bash
echo "#########################"
echo "Running entrypoint script"
echo "#########################"

# This is to emulate tty, for programs that require tty... gradio needs this.

# run additional scripts
{joined_script}

script -q /dev/null bash <<EOF
$@
EOF
echo "#########################"
echo "Finished entrypoint script"
echo "#########################"
"""
    return entrypoint_script


@injected
async def get_macro_entrypoint_installation(script: str):
    async def impl(cxt: BuildMacroContext) -> Macro:
        script_path = cxt.build_dir / "entrypoint.sh"
        script_path.write_text(script)
        return [
            RCopy(script_path, Path("/entrypoint.sh")),
            "RUN chmod +x /entrypoint.sh",
            # """ENTRYPOINT [\"/entrypoint.sh\"]"""
        ]

    return impl


@injected
async def docker_builder__for_rye_v2(
    docker__install_rye,
    macros_install_python_with_rye,
    macro_preinstall_from_requirements_with_rye,
    # macro_install_deps_via_staged_pyproject,
    storage_resolver,
    new_DockerBuilder,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
) -> DockerBuilder:
    """ """
    assert target.dirs[0].kind == "rye", (
        f"the first dir of the project must be rye. got {target.dirs[0].kind},{target.dirs[0].id}"
    )
    root_dir = target.dirs[0]
    root_path = await storage_resolver.locate(root_dir.id)

    pyproject_dir_in_container = Path("/sources") / root_dir.id

    return new_DockerBuilder(
        base_image=base_image,
        macros=[
            "ARG DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl git clang",
            await docker__install_rye(),
            await macros_install_python_with_rye(
                root_path / ".python-version", pyproject_dir_in_container
            ),
            await macro_preinstall_from_requirements_with_rye(
                base_image, target, pyproject_dir_in_container
            ),
            f"WORKDIR {target.default_working_dir}",
        ],
        scripts=[
            f". {pyproject_dir_in_container}/.venv/bin/activate",
        ],
    )


def build_base64_cmd(script: str):
    base64_script = base64.b64encode(script.encode("utf-8")).decode()
    cmd = "bash /usr/local/bin/base64_runner.sh " + base64_script
    return cmd


@injected
async def a_get_mount_request_for_pdir(
    storage_resolver,
    a_infer_source_kind,
    patch_uv_dir,
    patch_rye_project,
    /,
    placement: ProjectPlacement,
    pdir: ProjectDir,
) -> MountRequest:
    if pdir.kind == "auto":
        kind = await a_infer_source_kind(await storage_resolver.locate(pdir.id))
    elif pdir.kind == "auto-embed":
        # For auto-embed, we'll mount as source (no patching needed)
        # We could infer the actual kind but it's not needed since we treat it as source
        kind = "source"
    elif pdir.kind == "pyvenv-embed":
        # Treat pyvenv-embed as source mount (no patching needed)
        kind = "source"
    elif pdir.kind == "uv-pip-embed":
        # Treat uv-pip-embed as source mount (no patching needed)
        kind = "source"
    else:
        kind = pdir.kind

    @asynccontextmanager
    async def uv_impl():
        async with patch_uv_dir(tgt=pdir, placement=placement) as patched_pdir:
            yield patched_pdir

    @asynccontextmanager
    async def rye_impl():
        async with patch_rye_project(
            tgt=pdir, source_root=placement.sources_root
        ) as patched_pdir:
            yield patched_pdir

    match kind:
        case "source" | "resource" as kind:
            root = (
                placement.sources_root if kind == "source" else placement.resources_root
            )
            return ResolveMountRequest(
                kind=kind,
                resource_id=pdir.id,
                mount_point=root / pdir.id,
                excludes=pdir.excludes,
            )
        case "uv":
            uv_request = ContextualMountRequest(
                source=uv_impl,
                mount_point=placement.sources_root / pdir.id,
                excludes=pdir.excludes,
            )
            return uv_request
        case "rye":
            rye_request = ContextualMountRequest(
                source=rye_impl,
                mount_point=placement.sources_root / pdir.id,
                excludes=pdir.excludes,
            )
            return rye_request
        case "setup.py":
            return ResolveMountRequest(
                kind="source",
                resource_id=pdir.id,
                mount_point=placement.sources_root / pdir.id,
                excludes=pdir.excludes,
            )
        case _:
            raise ValueError(f"unknown kind {kind} for pdir {pdir.id}")


@injected
async def a_gather_mount_request_for_project(
    a_get_mount_request_for_pdir, /, project: ProjectDef
) -> tuple[MountRequest]:
    return await asyncio.gather(
        *[
            a_get_mount_request_for_pdir(placement=project.placement, pdir=pdir)
            for pdir in project.yield_project_dirs()
        ]
    )


@injected
async def schematics_with_rye(
    docker__install_rye,
    # macro_install_deps_via_staged_pyproject,
    a_gather_mount_request_for_project,
    new_DockerBuilder,
    macro_install_base64_runner,
    storage_resolver: IStorageResolver,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
) -> ContainerSchematic:
    """
    This schematic is designed to be used with rye.
    Requests sources to be mounted by env.
    Requests to cache uv and rye's python.
    Also requests to cache huggingface models.
    UV is going to be the solution, but we still need to use rye for now.
    """
    project_pyproject_dir = await storage_resolver.locate(target.dirs[0].id)
    hf_cache_mount = Path("/cache/huggingface")
    assert target.dirs[0].kind == "rye", (
        f"the first dir of the project must be rye. got {target.dirs[0].kind},{target.dirs[0].id}"
    )
    base_builder = new_DockerBuilder(
        base_image=base_image,
        base_stage_name="base",
        macros=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl git clang rsync",
            await docker__install_rye(),
            macro_install_base64_runner,
            f"ENV HF_HOME={hf_cache_mount}",
            f"WORKDIR {target.default_working_dir}",
            get_dummy_rye_venv(project_pyproject_dir),
        ],
        scripts=[
            f"cd {target.default_working_dir}",  # WORKDIR has no effect(often overriden) on K8S, so we set it here.
            # "source $HOME/.cargo/env", rye no longer uses $HOME/.cargo?
            "rye sync",
            # copy the dummy
            f". {target.default_working_dir}/.venv/bin/activate",
        ],
    )
    dynamic_mounts = await a_gather_mount_request_for_project(target)
    cache_mounts = [
        CacheMountRequest("uv_cache", Path("/root/.cache/uv")),
        CacheMountRequest("rye_python", Path("/opt/rye/py")),
        CacheMountRequest("hf_cache", hf_cache_mount),
    ]
    return ContainerSchematic(
        builder=base_builder, mount_requests=[*dynamic_mounts, *cache_mounts]
    )


__meta_design__ = design(overrides=ml_nexus_test_design)
