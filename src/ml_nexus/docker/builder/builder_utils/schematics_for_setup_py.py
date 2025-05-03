import asyncio
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pinjected import *

from ml_nexus.docker.builder.macros.macro_defs import RCopy, Macro
from ml_nexus.project_structure import ProjectDef
from ml_nexus.rsync_util import RsyncArgs
from ml_nexus.schematics import ContainerSchematic, CacheMountRequest, MountRequest, ContainerScript
from ml_nexus.testing import ml_nexus_test_design


@injected
async def schematics_with_setup_py(
        new_DockerBuilder,
        macro_install_base64_runner,
        a_macro_install_pyenv,
        gather_rsync_macros_project_def,
        a_get_mount_request_for_pdir,
        /,
        target: ProjectDef,
        base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
        python_version="3.12"
) -> ContainerSchematic:
    """
    This is to be used with project that only supports setup.py, due to native dependencies.
    Use pyenv to install python version.
    Preinstalls the project in editable mode into the container.
    Caches are mounted.
    """
    hf_cache_mount = Path("/cache/huggingface")
    assert target.dirs[
               0].kind == 'setup.py', f"the first dir of the project must be setup.py. got {target.dirs[0].kind},{target.dirs[0].id}"

    base_builder = new_DockerBuilder(
        base_image=base_image,
        base_stage_name='base',
        macros=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl",
            # "RUN apt-get install -y libgl1-mesa-glx",
            # "RUN apt-get install -y libglib2.0-0",
            # "RUN apt-get install -y libglib2.0-dev libgtk2.0-dev libsm6 libxext6 libxrender1 libfontconfig1 libice6",
            "RUN apt-get install -y git",
            "RUN apt-get install -y clang",
            "RUN apt-get install -y rsync",
            await a_macro_install_pyenv(python_version),
            macro_install_base64_runner,
            f'ENV HF_HOME={hf_cache_mount}',
            await gather_rsync_macros_project_def(target),
            f"WORKDIR {target.default_working_dir}",
            f"RUN python -m pip install -e ."
        ],
        scripts=[
            f"cd {target.default_working_dir}",  # WORKDIR has no effect(often overriden) on K8S, so we set it here.
            f"pyenv local {python_version}",
        ]
    )
    # sources are copied into the container so no dynamic mounts.
    # TODO mount resources
    resource_mounts = await asyncio.gather(*[a_get_mount_request_for_pdir(
        placement=target.placement, pdir=pdir
    ) for pdir in target.yield_project_dirs() if pdir.kind == 'resource']
                                           )
    cache_mounts = [
        CacheMountRequest(
            'hf_cache', hf_cache_mount
        ),
    ]
    return ContainerSchematic(
        builder=base_builder,
        mount_requests=[
            *cache_mounts,
            *resource_mounts
        ]
    )


@dataclass
class CommandWithMacro:
    command: str
    macro: Macro
    volumes: list[MountRequest]


@injected
async def macro_install_pyenv_virtualenv_installer(
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
        logger.warning(f"default pip cache dir: /root/.cache/pip is used. This is not going to work unless /root/.cache/pip is removable (Mounting docker volume to this dir won't work. mount the parent dir!)")
    command = f"""
export PYENV_ROOT={pyenv_root}
export PYTHON_VERSION={python_version}
export VENV_NAME={venv_name}
export VENV_PATH={venv_path}
export PIP_CACHE_DIR={pip_cache_dir}
{runnable_path}
echo ACTIVATING VENV at {venv_path}
source {venv_path}/bin/activate
"""
    script_path = Path(__file__).parent.parent.parent.parent / 'python_management/ensure_pyenv_virtualenv.sh'
    return CommandWithMacro(
        command,
        [
            f"""
RUN apt-get update
RUN apt-get install -y make build-essential libssl-dev zlib1g-dev \
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
            CacheMountRequest(
                'pyenv_installation', pyenv_root
            ),
            CacheMountRequest(
                f'venv_{venv_name}_{venv_id}', venv_path
            ),
            CacheMountRequest(
                f'pyenv_pip', pip_cache_dir.parent
            )
        ]
    )


@injected
async def schematics_with_pyvenv(
        new_DockerBuilder,
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
    Thi is to be used with persistent environments to test dependencies interactively.
    You can use this as a base to call setup.py.
    """
    hf_cache_mount = Path("/cache/huggingface")
    target_id = target.dirs[0].id
    # assert target.dirs[0].kind == 'setup.py', f"the first dir of the project must be setup.py. got {target.dirs[0].kind},{target.dirs[0].id}"
    venv_setup: CommandWithMacro = await macro_install_pyenv_virtualenv_installer(
        venv_name=target_id,
        venv_id=sha256(target_id.encode()).hexdigest()[:6],
        python_version=python_version
    )
    base_builder = new_DockerBuilder(
        base_image=base_image,
        base_stage_name='base',
        macros=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl",
            # "RUN apt-get install -y libgl1-mesa-glx",
            # "RUN apt-get install -y libglib2.0-0",
            # "RUN apt-get install -y libglib2.0-dev libgtk2.0-dev libsm6 libxext6 libxrender1 libfontconfig1 libice6",
            "RUN apt-get install -y git",
            "RUN apt-get install -y clang",
            "RUN apt-get install -y rsync",
            macro_install_base64_runner,
            venv_setup.macro,
            f'ENV HF_HOME={hf_cache_mount}',
            await gather_rsync_macros_project_def(target),
            f"WORKDIR {target.default_working_dir}",
        ],
        # await a_macro_install_pyenv(python_version),

        scripts=[
            venv_setup.command,
            f"cd {target.default_working_dir}",  # WORKDIR has no effect(often overriden) on K8S, so we set it here.
        ]
    )
    mounts = await asyncio.gather(*[a_get_mount_request_for_pdir(
        placement=target.placement, pdir=pdir
    ) for pdir in target.yield_project_dirs()]
                                  )
    cache_mounts = [
        CacheMountRequest(
            'hf_cache', hf_cache_mount
        ),
    ]
    return ContainerSchematic(
        builder=base_builder,
        mount_requests=[
            *cache_mounts,
            *mounts,
            *venv_setup.volumes
        ]
    )


@injected
async def schematics_with_setup_py__install_on_container(
        schematics_with_pyvenv,
        /,
        target: ProjectDef,
        base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
        python_version="3.12",
        run_pip_install=True
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


__meta_design__ = design(
    overrides=ml_nexus_test_design
)
