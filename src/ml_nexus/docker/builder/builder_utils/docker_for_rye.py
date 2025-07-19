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
from ml_nexus.schematics_util.universal import EnvComponent


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
async def docker_builder__for_rye_v2(  # noqa: PINJ006
    a_build_schematics_from_component,
    base_apt_packages_component,
    docker__install_rye,
    macros_install_python_with_rye,
    macro_preinstall_from_requirements_with_rye,
    storage_resolver,
    new_DockerBuilder,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
) -> DockerBuilder:
    """Build Docker container for rye projects using component system."""
    assert target.dirs[0].kind == "rye", (
        f"the first dir of the project must be rye. got {target.dirs[0].kind},{target.dirs[0].id}"
    )
    root_dir = target.dirs[0]
    root_path = await storage_resolver.locate(root_dir.id)

    pyproject_dir_in_container = Path("/sources") / root_dir.id

    # Create components
    rye_component = EnvComponent(
        installation_macro=[
            await docker__install_rye(),
            await macros_install_python_with_rye(
                root_path / ".python-version", pyproject_dir_in_container
            ),
            await macro_preinstall_from_requirements_with_rye(
                base_image, target, pyproject_dir_in_container
            ),
            f"WORKDIR {target.default_working_dir}",
        ],
        init_script=[
            f". {pyproject_dir_in_container}/.venv/bin/activate",
        ],
    )

    # Build schematic using component system
    schematic = await a_build_schematics_from_component(
        base_image=base_image,
        components=[
            base_apt_packages_component,  # This includes git_safe_directory_component
            rye_component,
        ],
    )

    # Extract the builder from the schematic
    return schematic.builder


def build_base64_cmd(script: str):
    base64_script = base64.b64encode(script.encode("utf-8")).decode()
    cmd = "bash /usr/local/bin/base64_runner.sh " + base64_script
    return cmd


async def _get_kind_from_pdir(
    pdir: ProjectDir, storage_resolver, a_infer_source_kind
) -> str:
    """Determine the actual kind for a project directory."""
    if pdir.kind == "auto":
        return await a_infer_source_kind(await storage_resolver.locate(pdir.id))
    elif pdir.kind in ["auto-embed", "pyvenv-embed", "uv-pip-embed"]:
        # Treat embed variants as source mount (no patching needed)
        return "source"
    else:
        return pdir.kind


def _create_mount_request_for_kind(
    kind: str, pdir: ProjectDir, placement: ProjectPlacement, uv_impl, rye_impl
) -> MountRequest:
    """Create appropriate mount request based on kind."""
    if kind in ["source", "resource"]:
        root = placement.sources_root if kind == "source" else placement.resources_root
        return ResolveMountRequest(
            kind=kind,
            resource_id=pdir.id,
            mount_point=root / pdir.id,
            excludes=pdir.excludes,
        )
    elif kind == "uv":
        return ContextualMountRequest(
            source=uv_impl,
            mount_point=placement.sources_root / pdir.id,
            excludes=pdir.excludes,
        )
    elif kind == "rye":
        return ContextualMountRequest(
            source=rye_impl,
            mount_point=placement.sources_root / pdir.id,
            excludes=pdir.excludes,
        )
    elif kind == "setup.py":
        return ResolveMountRequest(
            kind="source",
            resource_id=pdir.id,
            mount_point=placement.sources_root / pdir.id,
            excludes=pdir.excludes,
        )
    else:
        raise ValueError(f"unknown kind {kind} for pdir {pdir.id}")


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
    # Determine the actual kind
    kind = await _get_kind_from_pdir(pdir, storage_resolver, a_infer_source_kind)

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

    # Create and return the appropriate mount request
    return _create_mount_request_for_kind(kind, pdir, placement, uv_impl, rye_impl)


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
async def schematics_with_rye(  # noqa: PINJ006
    a_build_schematics_from_component,
    base_apt_packages_component,
    docker__install_rye,
    a_gather_mount_request_for_project,
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

    # Create components
    rye_component = EnvComponent(
        installation_macro=[
            await docker__install_rye(),
            f"WORKDIR {target.default_working_dir}",
            get_dummy_rye_venv(project_pyproject_dir),
        ],
        init_script=[
            f"cd {target.default_working_dir}",
            "rye sync",
            f". {target.default_working_dir}/.venv/bin/activate",
        ],
        mounts=[
            CacheMountRequest("uv_cache", Path("/root/.cache/uv")),
            CacheMountRequest("rye_python", Path("/opt/rye/py")),
        ],
    )

    base64_component = EnvComponent(installation_macro=[macro_install_base64_runner])

    hf_cache_component = EnvComponent(
        installation_macro=[f"ENV HF_HOME={hf_cache_mount}"],
        mounts=[CacheMountRequest("hf_cache", hf_cache_mount)],
    )

    # Build schematic using component system
    schematic = await a_build_schematics_from_component(
        base_image=base_image,
        components=[
            base_apt_packages_component,  # This includes git_safe_directory_component
            rye_component,
            base64_component,
            hf_cache_component,
        ],
    )

    # Add dynamic mounts
    dynamic_mounts = await a_gather_mount_request_for_project(target)
    schematic.mount_requests.extend(dynamic_mounts)

    return schematic


__meta_design__ = design(overrides=ml_nexus_test_design)
