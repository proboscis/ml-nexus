import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pinjected import *

from ml_nexus.docker.builder.macros.macro_defs import RCopy, Macro
from ml_nexus.project_structure import ProjectDef
from ml_nexus.schematics import (
    ContainerSchematic,
    CacheMountRequest,
    MountRequest,
    ContainerScript,
)
from ml_nexus.testing import ml_nexus_test_design
from ml_nexus.schematics_util.universal import EnvComponent


@injected
async def schematics_with_setup_py(  # noqa: PINJ006
    a_build_schematics_from_component,
    base_apt_packages_component,
    macro_install_base64_runner,
    a_macro_install_pyenv,
    gather_rsync_macros_project_def,
    a_get_mount_request_for_pdir,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    python_version="3.12",
) -> ContainerSchematic:
    """
    This is to be used with project that only supports setup.py, due to native dependencies.
    Use pyenv to install python version.
    Preinstalls the project in editable mode into the container.
    Caches are mounted.
    """
    hf_cache_mount = Path("/cache/huggingface")
    assert target.dirs[0].kind == "setup.py", (
        f"the first dir of the project must be setup.py. got {target.dirs[0].kind},{target.dirs[0].id}"
    )

    # Create components for this setup
    pyenv_component = EnvComponent(
        installation_macro=[await a_macro_install_pyenv(python_version)],
        init_script=[
            f"cd {target.default_working_dir}",
            f"pyenv local {python_version}",
        ],
    )

    base64_component = EnvComponent(installation_macro=[macro_install_base64_runner])

    hf_cache_component = EnvComponent(
        installation_macro=[f"ENV HF_HOME={hf_cache_mount}"],
        mounts=[CacheMountRequest("hf_cache", hf_cache_mount)],
    )

    project_sync_component = EnvComponent(
        installation_macro=[
            await gather_rsync_macros_project_def(target),
            f"WORKDIR {target.default_working_dir}",
            f"RUN python -m pip install -e .",
        ]
    )

    # Build schematic using component system
    schematic = await a_build_schematics_from_component(
        base_image=base_image,
        components=[
            base_apt_packages_component,  # This includes git_safe_directory_component
            pyenv_component,
            base64_component,
            hf_cache_component,
            project_sync_component,
        ],
    )

    # Add resource mounts
    resource_mounts = await asyncio.gather(
        *[
            a_get_mount_request_for_pdir(placement=target.placement, pdir=pdir)
            for pdir in target.yield_project_dirs()
            if pdir.kind == "resource"
        ]
    )
    schematic.mount_requests.extend(resource_mounts)

    return schematic


@dataclass
class CommandWithMacro:
    command: str
    macro: Macro
    volumes: list[MountRequest]


@injected
async def macro_install_pyenv_virtualenv_installer(  # noqa: PINJ006
    logger,
    /,
    venv_name,
    venv_id: str,  # this is to ensure venv identity.
    pyenv_root: Path = Path("/root/.pyenv"),
    pip_cache_dir: Path = Path("/root/pip_cache/pip"),
    python_version="3.12",
) -> CommandWithMacro:
    # we need globally unique identifier for venv path.
    runnable_path = Path("/ensure_pyenv_virtualenv.sh")
    venv_path = Path(f"/root/virtualenvs/{venv_name}_{venv_id}")
    # TODO handle multiple os/cpu architectures?
    # Currently we only assume the os is ubuntu and intel cpu.
    if pip_cache_dir == Path("/root/.cache/pip"):
        logger.warning(
            f"default pip cache dir: /root/.cache/pip is used. This is not going to work unless /root/.cache/pip is removable (Mounting docker volume to this dir won't work. mount the parent dir!)"
        )
    command = f"""
set -e  # Exit on error
export PYENV_ROOT={pyenv_root}
export PYTHON_VERSION={python_version}
export VENV_NAME={venv_name}
export VENV_PATH={venv_path}
export PIP_CACHE_DIR={pip_cache_dir}
{runnable_path}
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to setup pyenv virtualenv"
    exit 1
fi
echo ACTIVATING VENV at {venv_path}
source {venv_path}/bin/activate
"""
    script_path = (
        Path(__file__).parent.parent.parent.parent
        / "python_management/ensure_pyenv_virtualenv.sh"
    )
    return CommandWithMacro(
        command,
        [
            f"""
RUN apt-get update && apt-get install -y make build-essential libssl-dev zlib1g-dev \
            libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
            libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
            libffi-dev liblzma-dev git
""",
            RCopy(
                src=script_path,
                dst=runnable_path,
            ),
            f"RUN chmod +x {runnable_path}",
        ],
        [
            CacheMountRequest("pyenv_installation", pyenv_root),
            CacheMountRequest(f"venv_{venv_name}_{venv_id}", venv_path),
            CacheMountRequest(f"pyenv_pip", pip_cache_dir.parent),
        ],
    )


@injected
async def schematics_with_pyvenv(  # noqa: PINJ006
    a_build_schematics_from_component,
    base_apt_packages_component,
    macro_install_base64_runner,
    gather_rsync_macros_project_def,
    a_get_mount_request_for_pdir,
    macro_install_pyenv_virtualenv_installer,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    python_version="3.12",
) -> ContainerSchematic:
    """
    This creates pyenv-virtualenv environment, during runtime.
    This is to be used with persistent environments to test dependencies interactively.
    You can use this as a base to call setup.py.
    """
    hf_cache_mount = Path("/cache/huggingface")
    target_id = target.dirs[0].id
    venv_setup: CommandWithMacro = await macro_install_pyenv_virtualenv_installer(
        venv_name=target_id,
        venv_id=sha256(target_id.encode()).hexdigest()[:6],
        python_version=python_version,
    )

    # Create components
    base64_component = EnvComponent(installation_macro=[macro_install_base64_runner])

    venv_component = EnvComponent(
        installation_macro=[venv_setup.macro],
        init_script=[
            venv_setup.command,
            f"cd {target.default_working_dir}",
        ],
        mounts=venv_setup.volumes,
    )

    hf_cache_component = EnvComponent(
        installation_macro=[f"ENV HF_HOME={hf_cache_mount}"],
        mounts=[CacheMountRequest("hf_cache", hf_cache_mount)],
    )

    project_sync_component = EnvComponent(
        installation_macro=[
            await gather_rsync_macros_project_def(target),
            f"WORKDIR {target.default_working_dir}",
        ]
    )

    # Build schematic using component system
    schematic = await a_build_schematics_from_component(
        base_image=base_image,
        components=[
            base_apt_packages_component,  # This includes git_safe_directory_component
            base64_component,
            venv_component,
            hf_cache_component,
            project_sync_component,
        ],
    )

    # Add project mounts
    mounts = await asyncio.gather(
        *[
            a_get_mount_request_for_pdir(placement=target.placement, pdir=pdir)
            for pdir in target.yield_project_dirs()
        ]
    )
    schematic.mount_requests.extend(mounts)

    return schematic


@injected
async def schematics_with_setup_py__install_on_container(  # noqa: PINJ006
    schematics_with_pyvenv,
    /,
    target: ProjectDef,
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    python_version="3.12",
    run_pip_install=True,
) -> ContainerSchematic:
    """
    This is to be used with project that only supports setup.py, due to native dependencies.
    Use pyenv to install python version.
    Preinstalls the project in editable mode into the container.
    Caches are mounted.
    """
    schem = await schematics_with_pyvenv(
        target=target,
        base_image=base_image,
        python_version=python_version,
    )
    if run_pip_install:
        schem += ContainerScript("python -m pip install -e .")
    return schem


__meta_design__ = design(overrides=ml_nexus_test_design)
