import asyncio
from dataclasses import field, dataclass
from hashlib import sha256
from itertools import chain
from pathlib import Path
from typing import Optional, List, Protocol

from beartype import beartype
from loguru import logger
from pinjected import *

from ml_nexus import load_env_design
from ml_nexus.docker.builder.builder_utils.rye_util import get_dummy_rye_venv
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import MountRequest, CacheMountRequest, ContainerSchematic
from ml_nexus.schematics_util.env_identification import SetupScriptWithDeps
from ml_nexus.storage_resolver import IStorageResolver
from typing import Sequence

"""
We create a function that generates a schematics for universal project structure.

1. check the target dir to see the project structure
2. automatically choose and build schematics
"""


@dataclass
class EnvComponent:
    installation_macro: Macro = field(default_factory=list)
    init_script: list[str] = field(default_factory=list)
    mounts: List[MountRequest] = field(default_factory=list)
    dependencies: List['EnvComponent'] = field(default_factory=list)


@injected
async def a_hf_cache_component(cache_name: str = 'hf_cache',
                               container_path: Path = Path('/cache/huggingface')) -> EnvComponent:
    return EnvComponent(
        installation_macro=[
            f"ENV HF_HOME={container_path}"
        ],
        mounts=[CacheMountRequest(
            cache_name, container_path
        )]
    )


@instance
async def base_apt_packages_component():
    return EnvComponent(
        installation_macro=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl",
            "RUN apt-get install -y libgl1-mesa-glx",
            "RUN apt-get install -y libglib2.0-0",
            "RUN apt-get install -y libglib2.0-dev libgtk2.0-dev libsm6 libxext6 libxrender1 libfontconfig1 libice6",
            "RUN apt-get install -y git",
            "RUN apt-get install -y clang",
            "RUN apt-get install -y rsync",
        ],
    )


@injected
async def a_pyenv_component(
        macro_install_pyenv_virtualenv_installer,
        base_apt_packages_component,
        /,
        target: ProjectDef,
        python_version: str = "3.12",
):
    target_id = target.dirs[0].id
    venv_setup = await macro_install_pyenv_virtualenv_installer(
        venv_name=target_id,
        venv_id=sha256(target_id.encode()).hexdigest()[:6],
        python_version=python_version,
        pip_cache_dir=Path("/root/pip_cache/pip")
    )
    return EnvComponent(
        installation_macro=[
            venv_setup.macro
        ],
        init_script=[
            f"cd {target.default_working_dir}",
            venv_setup.command
        ],
        dependencies=[base_apt_packages_component],
        mounts=venv_setup.volumes
    )


@instance
async def base64_runner_component(macro_install_base64_runner):
    return EnvComponent(
        installation_macro=[macro_install_base64_runner]
    )


@injected
@beartype
async def a_build_schematics_from_component(
        new_DockerBuilder,
        /,
        base_image: str,
        components: List[EnvComponent],
) -> ContainerSchematic:
    visited = set()
    topo_sorted = []

    def dfs(components: List[EnvComponent]):
        for c in components:
            if id(c) in visited:
                continue
            visited.add(id(c))
            dfs(c.dependencies)
            topo_sorted.append(c)

    dfs(components)

    base_builder = new_DockerBuilder(
        base_image=base_image,
        base_stage_name='base',
        macros=[c.installation_macro for c in topo_sorted],
        scripts=list(chain(*[c.init_script for c in topo_sorted]))
    )
    mounts = list(chain(*[c.mounts for c in topo_sorted]))
    return ContainerSchematic(
        builder=base_builder,
        mount_requests=mounts
    )


@injected
@beartype
async def a_project_sync_component(
        a_get_mount_request_for_pdir,
        /,
        tgt: ProjectDef) -> EnvComponent:
    import asyncio
    mounts = await asyncio.gather(*[a_get_mount_request_for_pdir(
        placement=tgt.placement, pdir=pdir
    ) for pdir in tgt.yield_project_dirs() if pdir.kind == 'resource'])
    return EnvComponent(
        mounts=list(mounts)
    )


test_a_build_schematics_from_component: IProxy = a_build_schematics_from_component(
    base_image='nvidia/cuda:12.3.1-devel-ubuntu22.04',
    components=Injected.list(
        a_project_sync_component(tgt=(project := ProjectDef(dirs=[ProjectDir('src', kind='resource')]))),
        a_pyenv_component(project, python_version='3.12'),
        a_hf_cache_component(),
        base64_runner_component,
    )
)


@injected
async def a_rye_component(
        docker__install_rye,
        base_apt_packages_component,
        ml_nexus_github_credential_component,
        /,
        project_workdir: Path,
        local_project_dir: Path
):
    caches = [
        CacheMountRequest(
            'uv_cache', Path('/root/.cache/uv')
        ),
        CacheMountRequest(
            'rye_python', Path('/opt/rye/py')
        )
    ]
    return EnvComponent(
        installation_macro=[
            await docker__install_rye(),
            f"WORKDIR {project_workdir}",
            get_dummy_rye_venv(local_project_dir)  # is it alright to do this in Dockerfile? wont this get overwritten?
        ],
        init_script=[
            f"cd {project_workdir}",
            f"rye sync",
            f". {project_workdir}/.venv/bin/activate"
        ],
        mounts=caches,
        dependencies=[base_apt_packages_component, ml_nexus_github_credential_component]
    )


@instance
async def rust_cargo_component(

):
    return EnvComponent(
        installation_macro=[
            'RUN apt-get update && apt-get install -y curl',
            "RUN curl https://sh.rustup.rs -sSf | sh -s -- -y",
        ]
    )


@instance
def ml_nexus_github_credential_component(logger) -> EnvComponent:
    # do nothing by default
    logger.warning(
        f"No github credential is being used. override `ml_nexus_github_credential_component:EnvComponent` to override it.")
    return EnvComponent()


@injected
async def a_uv_component(
        a_macro_install_uv,
        base_apt_packages_component,
        rust_cargo_component,
        ml_nexus_github_credential_component: EnvComponent,
        /,
        target: ProjectDef

):
    caches = [
        CacheMountRequest(
            'uv_cache', Path('/root/.cache/uv')
        ),
        CacheMountRequest(
            'uv_venv', Path('/root/.cache/uv_venv')
        )
    ]
    return EnvComponent(
        installation_macro=[
            await a_macro_install_uv()
        ],
        dependencies=[
            rust_cargo_component,
            base_apt_packages_component,
            ml_nexus_github_credential_component]
        ,
        init_script=[
            f"cd {target.default_working_dir}",  # WORKDIR has no effect on K8S, so we set it here.
            "source $HOME/.cargo/env",
            f"RANDOM_ID=$(date +%s)",
            f"export VIRTUAL_ENV=/root/.cache/uv_venv/$RANDOM_ID",
            "uv --version",
            "uv sync",
            f"source '$VIRTUAL_ENV/bin/activate'"
        ],
        mounts=caches
    )


test_a_build_schematics_from_component_uc: IProxy[ContainerSchematic] = a_build_schematics_from_component(
    base_image='ubuntu:20.04',
    components=Injected.list(
        a_project_sync_component(tgt=(project := ProjectDef(dirs=[ProjectDir('src', kind='uv')]))),
        a_uv_component(project),
        a_hf_cache_component(),
        base64_runner_component,
    )
).builder.a_build("test_image", use_cache=False)


@injected
async def a_component_to_install_requirements_txt(
        storage_resolver: IStorageResolver,
        logger,
        /,
        target: ProjectDef
):
    local_path = await storage_resolver.locate(target.dirs[0].id)
    requirements_txt_path = local_path / 'requirements.txt'
    requirements = requirements_txt_path.read_text()
    init_script = []
    packages = [r.split('#')[0].strip() for r in requirements.split('\n')]
    # handle xformers separately
    common_packages = []
    special_packages = []
    for p in packages:
        if 'xformers' in p:
            special_packages.append(p)
        else:
            common_packages.append(p)
    logger.info(f"common packages:{common_packages}")
    logger.info(f"special packages:{special_packages}")
    common_packages_str = " ".join([f"'{pkg}'" for pkg in common_packages if pkg])
    special_install_lines = ""
    for p in special_packages:
        special_install_lines += f"pip install {p} --no-dependencies\n"
    init_script.append(
        f"""
        cd {target.default_working_dir}
        pip install {common_packages_str}
        {special_install_lines}
        echo "requirements.txt installed"
        """
    )
    return EnvComponent(
        init_script=init_script
    )


class SchematicsUniversal(Protocol):
    async def __call__(self, target: ProjectDef, base_image: Optional[str] = None,
                       python_version: Optional[str] = None) -> ContainerSchematic:
        ...


@injected
async def schematics_universal(
        a_hf_cache_component,
        base_apt_packages_component,
        a_pyenv_component,
        base64_runner_component,
        a_project_sync_component,
        a_build_schematics_from_component,
        a_prepare_setup_script_with_deps,
        a_rye_component,
        a_uv_component,
        storage_resolver: IStorageResolver,
        ml_nexus_default_base_image: str,
        ml_nexus_default_python_version: str,
        a_get_mount_request_for_pdir,
        a_component_to_install_requirements_txt,
        /,
        target: ProjectDef,
        base_image: Optional[str] = None,
        python_version: Optional[str] = None,
        additional_components: Sequence[EnvComponent] = (),
):
    base_image = base_image or ml_nexus_default_base_image
    python_version = python_version or ml_nexus_default_python_version
    local_root_dir = await storage_resolver.locate(target.dirs[0].id)
    setup_script_with_deps: SetupScriptWithDeps = await a_prepare_setup_script_with_deps(local_root_dir)
    python_components = []
    for dep in setup_script_with_deps.env_deps:
        match dep:
            case 'pyvenv':
                python_components.append(
                    await a_pyenv_component(target=target, python_version=python_version)
                )
            case 'requirements.txt':
                """
                we need to have a dedicated installer for requirements.txt
                Because xformers cannot be installed without torch!
                We might need a dedicated uv project initialization, instead of using direct requirements.
                That's a TODO for now.
                """
                python_components.append(
                    await a_component_to_install_requirements_txt(target=target)
                )
            case 'setup.py':
                python_components.append(
                    EnvComponent(
                        init_script=[
                            f"cd {target.default_working_dir}",
                            "pip install -e ."
                        ]
                    )
                )
            case 'rye':
                local_project_dir = await storage_resolver.locate(target.dirs[0].id)
                python_components.append(
                    await a_rye_component(project_workdir=target.default_working_dir,
                                          local_project_dir=local_project_dir)
                )
            case 'uv':
                python_components.append(
                    await a_uv_component(target=target)
                )
            case 'poetry':
                raise NotImplementedError("poetry is not supported yet")

    mounts = await asyncio.gather(*[a_get_mount_request_for_pdir(
        placement=target.placement, pdir=pdir
    ) for pdir in target.yield_project_dirs()])
    setup_component = EnvComponent(
        dependencies=python_components,
        mounts=list(mounts)
    )

    components = [
        base64_runner_component,
        base_apt_packages_component,
        await a_hf_cache_component(),
        setup_component,
        await a_project_sync_component(tgt=target),
        *additional_components
    ]
    return await a_build_schematics_from_component(
        base_image=base_image,
        components=components
    )


test_build_schematics_universal: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir('pinjected_openai', kind='auto')]),
)
test_docker_env: IProxy = injected(DockerEnvFromSchematics)(
    project=ProjectDef(dirs=[ProjectDir('pinjected_openai', kind='auto')]),
    schematics=test_build_schematics_universal,
    docker_host='zeus'
)
test_docker_env_run: IProxy = test_docker_env.run_script("""
ls -lah
""")
test_requirements_project: IProxy = ProjectDef(
    dirs=[
        ProjectDir(
            id='sketch2lineart',
            kind='auto',
            dependencies=[]
        )
    ]
)
test_schematics_req_txt: IProxy = schematics_universal(
    target=test_requirements_project
)
test_req_txt_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_requirements_project,
    schematics=test_schematics_req_txt,
    docker_host='zeus',
    container_name='test_req_txt_docker'
)
test_req_txt_docker_run: IProxy = test_req_txt_docker.run_script(
    """
ls -lah
"""
)

__meta_design__ = design(
    overrides=load_env_design + design(
        logger=logger
    )
)
