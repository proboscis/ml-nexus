from pathlib import Path

from pinjected import *

from ml_nexus import load_env_design
from ml_nexus.docker.builder.docker_builder import DockerBuilder
from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.docker_env import default_ignore_set, DockerHostEnvironment
from ml_nexus.project_structure import ProjectDef, ProjectDir

macro_essentials = [
    "ARG DEBIAN_FRONTEND=noninteractive",
    "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl",
    "RUN apt-get install -y libgl1-mesa-glx",
    "RUN apt-get install -y libglib2.0-0",
    "RUN apt-get install -y libglib2.0-dev libgtk2.0-dev libsm6 libxext6 libxrender1 libfontconfig1 libice6",
    "RUN apt-get install -y git",
    "RUN apt-get install -y clang"
]

pyenv_cache_paths = [
    # Path("/root/.pyenv"),
    Path("/root/.pyenv/cache"),
    Path("/root/.pyenv/versions"),
    Path("/root/.pyenv/shims")
]


@injected
async def a_macro_install_pyenv(
        RUN_with_cache,
        /,
        python_version: str
):
    """
    Poetry is not supported for 3.6. so forget about it!
    :param python_version:
    :return:
    """
    # TODO WARNING you tried to cache pyenv build, but faild! beware! 20240816.
    # I think it's better to use rye if the python version >= 3.7 (Rye's limitation)
    # So, we should switch the docker image builder and its tempalte...
    # The build takes 6 minutes, on ubuntu
    return [
        "ENV DEBIAN_FRONTEND=noninteractive",
        # Install dependencies
        f"RUN apt-get update && apt-get install -y "
        "make build-essential libssl-dev zlib1g-dev libbz2-dev "
        "libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev "
        "libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev "
        "python3-openssl git",
        # Install pyenv
        "RUN curl https://pyenv.run | bash",
        # RUN_with_cache(pyenv_cache_paths, "curl https://pyenv.run | bash"),
        # Set up pyenv environment variables
        "ENV HOME=/root",
        "ENV PYENV_ROOT=$HOME/.pyenv",
        "ENV PATH=$PYENV_ROOT/bin:$PATH",
        "RUN pyenv -h",
        "RUN apt install tree -y",
        # RUN_with_cache(pyenv_cache_paths, "echo 'eval \"$(pyenv init --path)\"' >> ~/.bashrc"),
        # RUN_with_cache(pyenv_cache_paths, "echo 'eval \"$(pyenv virtualenv-init -)\"' >> ~/.bashrc"),
        """
        RUN echo 'eval "$(pyenv init --path)"' >> ~/.bashrc && echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc
        """,
        'SHELL ["/bin/bash","--login", "-c"]',
        'RUN source ~/.bashrc && pyenv -h',
        'RUN pyenv -h',
        'ENV MAKE_OPTS="-j 32"',
        "ENV PYTHON_BUILD_HARDENING=1",
        f"RUN pyenv install {python_version}",
        f"RUN pyenv global {python_version}",
        # RUN_with_cache(pyenv_cache_paths, f"pyenv install {python_version} --skip-existing"),
        # RUN_with_cache(pyenv_cache_paths, f"cp -R /root/.pyenv/versions/{python_version} /pyenv_python"),
        # RUN_with_cache(pyenv_cache_paths, f"cp -R /root/.pyenv/shims /pyenv_shims"),
        f"ENV PATH=$PYENV_ROOT/shims:$PATH",
        f"RUN which python",
    ]


@injected
async def a_macro_install_uv():
    return [
        "RUN curl -LsSf https://astral.sh/uv/install.sh | sh",
        "RUN echo 'source $HOME/.cargo/env' >> ~/.bashrc",
        "RUN . $HOME/.cargo/env",
        'ENV PATH="/root/.cargo/bin:${PATH}"',
        "RUN uv --version"
    ]


@injected
def RUN_with_cache(cache_paths: list[Path], cmd):
    cache_opts = " ".join([f"--mount=type=cache,target={str(p)}" for p in cache_paths])
    return f"RUN {cache_opts} {cmd}"


@injected
def macro_uv_command(
        RUN_with_cache,
        /,
        cmd):
    uv_pip_caches = [
        Path("/root/.cache/uv"),
        Path("/root/.cache/pip")
    ]
    return [
        RUN_with_cache(uv_pip_caches, f"uv {cmd}"),
    ]


@injected
def macro_uv_pip_install(
        macro_uv_command,
        /,
        pip_deps: list[str]):
    dep_str = [f'"{d}"' for d in pip_deps if d]
    if dep_str:
        return macro_uv_command(
            f"pip install {' '.join(dep_str)}"
        )
    return []


@injected
async def a_macro_setup_python_for_project_via_uv(
        macro_uv_pip_install,
        /,
        python_version,
        pip_deps: list[str],
        venv_dir: Path,
        pip_stage_prefixes: list[str] = ("torch", "tensorflow")
):
    assert venv_dir.name == ".venv", f"venv_dir must end with .venv, but got {venv_dir}"
    py_version_tuple = tuple(map(int, python_version.split(".")))
    macros = [
        f"RUN apt install tree -y",
        f"WORKDIR {venv_dir.parent}",
        f"RUN pyenv global {python_version}",
        f"RUN uv venv",
        f'RUN python -c "import sys; print(sys.version_info); assert sys.version_info[:2] == {py_version_tuple[:2]}"'
        # macro_uv_pip_install(pip_deps),
    ]
    for stage in pip_stage_prefixes:
        deps = [p for p in pip_deps if p.startswith(stage)]
        macros += [
            f"LABEL PIP_STAGE={stage}",
            macro_uv_pip_install(deps)
        ]
    macros += [macro_uv_pip_install(pip_deps)]
    return macros


@injected
async def a_builder_python_project_with_uv(
        a_macro_install_pyenv,
        a_macro_install_uv,
        a_macro_setup_python_for_project_via_uv,
        new_DockerBuilder,
        gather_rsync_macros_project_def,
        /,
        base_image: str,
        project: ProjectDef,
        python_version,
        packages: list[str],
        venv_dir: Path,
        macro_before_uv: Macro = None
) -> DockerBuilder:
    if macro_before_uv is None:
        macro_before_uv = []
    macro = [
        macro_essentials,
        await a_macro_install_pyenv(python_version),
        await a_macro_install_uv(),
        macro_before_uv,
        await a_macro_setup_python_for_project_via_uv(python_version, packages, venv_dir),
        await gather_rsync_macros_project_def(project)
    ]
    return new_DockerBuilder(
        base_image=base_image,
        macros=macro,
        scripts=[
            f"""
cd {venv_dir.parent}
source .venv/bin/activate
cd {project.default_working_dir}
"""
        ]
    )


_pyenv_uv_project = ProjectDef(
    dirs=[
        ProjectDir(
            id="ml-nexus",
            kind="source",
            dependencies=[],
            excludes=default_ignore_set
        )
    ]
)

_pyenv_uv_docker = a_builder_python_project_with_uv(
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    project=_pyenv_uv_project,
    python_version="3.8.12",
    packages=["poetry", "torch", "uv"],
    venv_dir=_pyenv_uv_project.placement.sources_root / "ml-nexus" / ".venv"
)

_docker_env = injected(DockerHostEnvironment)(
    project=_pyenv_uv_project,
    docker_builder=_pyenv_uv_docker,
    docker_host=injected('ml_nexus_test_docker_host')
)

_sam2_project = ProjectDef(
    dirs=[
        ProjectDir(
            id="segment-anything-2",
            kind="source",
            dependencies=[],
            excludes=default_ignore_set
        )
    ]
)
venv_path = _sam2_project.placement.sources_root / "segment-anything-2" / ".venv"

# oh it worked, cool.
test_docker_env: IProxy = _docker_env.run_script(
    """
    nvidia-smi
    which python
    python --version
    """
)

__meta_design__ = design(
    overrides=load_env_design + design(
        docker_build_name='ml-nexus',
    )
)
