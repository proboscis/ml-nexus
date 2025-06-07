import asyncio
from dataclasses import field, dataclass
from hashlib import sha256
from itertools import chain
from pathlib import Path
from typing import Optional, List, Protocol, Callable, Sequence, TYPE_CHECKING

from beartype import beartype
from loguru import logger
from pinjected import *

if TYPE_CHECKING:
    from ml_nexus.rsync_util import NewRsyncArgs
    import loguru

from ml_nexus import load_env_design
from ml_nexus.docker.builder.builder_utils.rye_util import get_dummy_rye_venv
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.macros.macro_defs import Macro, RCopy
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics
from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.schematics import MountRequest, CacheMountRequest, ContainerSchematic
from ml_nexus.schematics_util.env_identification import SetupScriptWithDeps
from ml_nexus.storage_resolver import IStorageResolver

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
    dependencies: List["EnvComponent"] = field(default_factory=list)


@injected
async def a_hf_cache_component(
    cache_name: str = "hf_cache", container_path: Path = Path("/cache/huggingface")
) -> EnvComponent:
    return EnvComponent(
        installation_macro=[f"ENV HF_HOME={container_path}"],
        mounts=[CacheMountRequest(cache_name, container_path)],
    )


@instance
async def base_apt_packages_component() -> EnvComponent:
    return EnvComponent(
        installation_macro=[
            "ENV DEBIAN_FRONTEND=noninteractive",
            # Install all dependencies required by pyenv to build Python from source
            "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl git clang rsync \
                zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget llvm libncurses5-dev libncursesw5-dev \
                xz-utils tk-dev libffi-dev liblzma-dev python3-openssl",
        ],
    )


@injected
async def a_pyenv_component(
    macro_install_pyenv_virtualenv_installer: Callable,
    base_apt_packages_component: EnvComponent,
    /,
    target: ProjectDef,
    python_version: str = "3.12",
) -> EnvComponent:
    target_id = target.dirs[0].id
    # Sanitize target_id for use as venv name (replace slashes and other problematic chars)
    sanitized_venv_name = (
        target_id.replace("/", "_").replace("\\", "_").replace(" ", "_")
    )

    venv_setup = await macro_install_pyenv_virtualenv_installer(
        venv_name=sanitized_venv_name,
        venv_id=sha256(target_id.encode()).hexdigest()[:6],
        python_version=python_version,
        pip_cache_dir=Path("/root/pip_cache/pip"),
    )
    return EnvComponent(
        installation_macro=[venv_setup.macro],
        init_script=[f"cd {target.default_working_dir}", venv_setup.command],
        dependencies=[base_apt_packages_component],
        mounts=venv_setup.volumes,
    )


@injected
async def a_pyenv_component_embedded(
    base_apt_packages_component: EnvComponent,
    storage_resolver: IStorageResolver,
    new_RsyncArgs: "NewRsyncArgs",
    logger: "loguru.Logger",
    /,
    target: ProjectDef,
    python_version: str = "3.12",
) -> EnvComponent:
    """
    Pyenv component with embedded dependencies using multi-stage Docker build.
    This optimizes build caching by separating dependency installation from source code.

    Docker layer structure:
    1. Layer 1: Install build dependencies
    2. Layer 2: Install pyenv (without cache mounts for embedded)
    3. Layer 3: Install Python version
    4. Layer 4: Create virtualenv and install dependencies
    5. Layer 5: Copy source code
    6. Layer 6: Install package with setup.py (if exists)

    This ensures that pyenv installation is properly cached in image layers.
    """
    target_id = target.dirs[0].id
    local_project_dir = await storage_resolver.locate(target.dirs[0].id)

    # Sanitize target_id for use as venv name (replace slashes and other problematic chars)
    sanitized_venv_name = (
        target_id.replace("/", "_").replace("\\", "_").replace(" ", "_")
    )

    # For embedded components, we need to install pyenv directly in the image
    # without relying on cache mounts
    pyenv_root = Path("/root/.pyenv")
    venv_path = Path(
        f"/root/virtualenvs/{sanitized_venv_name}_{sha256(target_id.encode()).hexdigest()[:6]}"
    )

    # Build pyenv installation macros (without cache mounts for embedded)
    pyenv_install_macros = [
        # Install build dependencies
        f"""
RUN apt-get update && apt-get install -y make build-essential libssl-dev zlib1g-dev \\
            libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \\
            libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \\
            libffi-dev liblzma-dev git
""",
        # Clone pyenv directly (no cache mount)
        f"RUN git clone https://github.com/pyenv/pyenv.git {pyenv_root}",
        # Set up pyenv environment
        f"ENV PYENV_ROOT={pyenv_root}",
        f"ENV PATH=$PYENV_ROOT/bin:$PATH",
        # Install Python version (using proper shell evaluation)
        f'RUN bash -c \'eval "$(pyenv init --path)" && eval "$(pyenv init -)" && pyenv install {python_version} && pyenv global {python_version}\'',
        # Create virtualenv directory
        f"RUN mkdir -p /root/virtualenvs",
        # Create the virtualenv (ensure pyenv Python is used)
        f'RUN bash -c \'eval "$(pyenv init --path)" && eval "$(pyenv init -)" && python -m venv {venv_path}\'',
    ]

    # Check for dependency files
    requirements_path = local_project_dir / "requirements.txt"
    setup_py_path = local_project_dir / "setup.py"

    # Build dependency installation layer
    dependency_install_macro = []
    if requirements_path.exists():
        # Copy requirements.txt and install dependencies
        dependency_install_macro = [
            RCopy(
                src=requirements_path,
                dst=Path(target.default_working_dir) / "requirements.txt",
            ),
            f"WORKDIR {target.default_working_dir}",
            # Activate venv and install requirements (with pip cache for faster rebuilds)
            f'RUN --mount=type=cache,target=/root/pip_cache/pip bash -c \'eval "$(pyenv init --path)" && eval "$(pyenv init -)" && source {venv_path}/bin/activate && pip install --upgrade pip && pip install -r requirements.txt\'',
        ]

    # Copy all project files (excluding common build artifacts)
    project_copy_macro = [
        new_RsyncArgs(
            src=local_project_dir,
            dst=Path(target.default_working_dir),
            excludes=[
                "__pycache__",
                "*.pyc",
                ".git",
                ".ruff_cache",
                ".pytest_cache",
                "build",
                "dist",
                "*.egg-info",
                ".mypy_cache",
                ".tox",
                ".coverage",
                "htmlcov",
                ".cache",
                "node_modules",
                ".env",
                ".DS_Store",
                "venv",
                "env",
                ".venv",
                ".pyenv",
            ],
        )
    ]

    # If setup.py exists, install it after source code is copied
    final_install = []
    if setup_py_path.exists():
        # Activate venv and install package
        final_install.append(
            f'RUN --mount=type=cache,target=/root/pip_cache/pip bash -c \'eval "$(pyenv init --path)" && eval "$(pyenv init -)" && source {venv_path}/bin/activate && cd {target.default_working_dir} && pip install -e .\''
        )

    # For embedded components, pyenv is already installed in the image
    # We need to initialize pyenv and activate the virtualenv at runtime
    activation_script = f"""
echo "Initializing pyenv..."
export PYENV_ROOT=/root/.pyenv
export PATH=$PYENV_ROOT/bin:$PATH
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
echo "ACTIVATING VENV at {venv_path}"
source {venv_path}/bin/activate
"""

    return EnvComponent(
        installation_macro=[
            *pyenv_install_macros,  # Install pyenv and create venv
            *dependency_install_macro,  # Install dependencies
            *project_copy_macro,  # Copy source code
            *final_install,  # Install package if setup.py exists
        ],
        init_script=[f"cd {target.default_working_dir}", activation_script.strip()],
        dependencies=[base_apt_packages_component],
        mounts=[],  # No cache mounts for embedded components - everything is in the image
    )


@instance
async def base64_runner_component(macro_install_base64_runner: Macro) -> EnvComponent:
    return EnvComponent(installation_macro=[macro_install_base64_runner])


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
        base_stage_name="base",
        macros=[c.installation_macro for c in topo_sorted],
        scripts=list(chain(*[c.init_script for c in topo_sorted])),
    )
    mounts = list(chain(*[c.mounts for c in topo_sorted]))
    return ContainerSchematic(builder=base_builder, mount_requests=mounts)


@injected
@beartype
async def a_project_sync_component(
    a_get_mount_request_for_pdir, /, tgt: ProjectDef
) -> EnvComponent:
    import asyncio

    mounts = await asyncio.gather(
        *[
            a_get_mount_request_for_pdir(placement=tgt.placement, pdir=pdir)
            for pdir in tgt.yield_project_dirs()
            if pdir.kind == "resource"
        ]
    )
    return EnvComponent(mounts=list(mounts))


test_a_build_schematics_from_component: IProxy = a_build_schematics_from_component(
    base_image="nvidia/cuda:12.3.1-devel-ubuntu22.04",
    components=Injected.list(
        a_project_sync_component(
            tgt=(project := ProjectDef(dirs=[ProjectDir("src", kind="resource")]))
        ),
        a_pyenv_component(project, python_version="3.12"),
        a_hf_cache_component(),
        base64_runner_component,
    ),
)


@injected
async def a_rye_component(
    docker__install_rye: Callable,
    base_apt_packages_component: EnvComponent,
    ml_nexus_github_credential_component: EnvComponent,
    /,
    project_workdir: Path,
    local_project_dir: Path,
) -> EnvComponent:
    caches = [
        CacheMountRequest("uv_cache", Path("/root/.cache/uv")),
        CacheMountRequest("rye_python", Path("/opt/rye/py")),
    ]
    return EnvComponent(
        installation_macro=[
            await docker__install_rye(),
            f"WORKDIR {project_workdir}",
            get_dummy_rye_venv(
                local_project_dir
            ),  # is it alright to do this in Dockerfile? wont this get overwritten?
        ],
        init_script=[
            f"cd {project_workdir}",
            "rye sync",
            f". {project_workdir}/.venv/bin/activate",
        ],
        mounts=caches,
        dependencies=[
            base_apt_packages_component,
            ml_nexus_github_credential_component,
        ],
    )


@instance
async def rust_cargo_component() -> EnvComponent:
    return EnvComponent(
        installation_macro=[
            "RUN apt-get update && apt-get install -y curl",
            "RUN curl https://sh.rustup.rs -sSf | sh -s -- -y",
        ]
    )


@instance
def ml_nexus_github_credential_component(logger: "loguru.Logger") -> EnvComponent:
    # do nothing by default
    logger.warning(
        "No github credential is being used. override `ml_nexus_github_credential_component:EnvComponent` to override it."
    )
    return EnvComponent()


@injected
async def a_uv_component(
    a_macro_install_uv: Callable,
    base_apt_packages_component: EnvComponent,
    rust_cargo_component: EnvComponent,
    ml_nexus_github_credential_component: EnvComponent,
    /,
    target: ProjectDef,
    do_sync: bool = True,
    isolate_env: bool = True,
) -> EnvComponent:
    caches = [
        CacheMountRequest("uv_cache", Path("/root/.cache/uv")),
        CacheMountRequest("uv_venv", Path("/root/.cache/uv_venv")),
    ]
    scripts = []
    if isolate_env:
        scripts += [
            "RANDOM_ID=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)",
            "export UV_PROJECT_ENVIRONMENT=/root/.cache/uv_venv/$RANDOM_ID",
        ]
    else:
        scripts += ["export UV_PROJECT_ENVIRONMENT=/root/.cache/uv_venv/default"]
    if do_sync:
        scripts += ["uv sync", "source $UV_PROJECT_ENVIRONMENT/bin/activate"]
    return EnvComponent(
        installation_macro=[await a_macro_install_uv()],
        dependencies=[
            rust_cargo_component,
            base_apt_packages_component,
            ml_nexus_github_credential_component,
        ],
        init_script=[
            f"cd {target.default_working_dir}",  # WORKDIR has no effect on K8S, so we set it here.
            "source $HOME/.cargo/env",
            "uv self update",
            *scripts,
        ],
        mounts=caches,
    )


@injected
async def a_uv_component_embedded(
    a_macro_install_uv: Callable,
    base_apt_packages_component: EnvComponent,
    rust_cargo_component: EnvComponent,
    ml_nexus_github_credential_component: EnvComponent,
    storage_resolver: IStorageResolver,
    new_RsyncArgs: "NewRsyncArgs",
    /,
    target: ProjectDef,
    do_sync: bool = True,
    isolate_env: bool = True,
) -> EnvComponent:
    """
    UV component with embedded dependencies using multi-stage Docker build.
    This optimizes build caching by separating dependency installation from source code.
    """
    # Get the local project directory
    local_project_dir = await storage_resolver.locate(target.dirs[0].id)

    # Create macro for dependency caching stage
    dependency_copy_macros = []

    # Copy only dependency files first
    dependency_files = ["pyproject.toml", "uv.lock", "Cargo.toml", "Cargo.lock"]
    for dep_file in dependency_files:
        src_path = local_project_dir / dep_file
        if src_path.exists():
            dependency_copy_macros.append(
                RCopy(src=src_path, dst=Path(target.default_working_dir) / dep_file)
            )

    # Install dependencies only (with BuildKit cache mount)
    dependency_install_macro = [
        *dependency_copy_macros,
        f"WORKDIR {target.default_working_dir}",
        "RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-install-project",
    ]

    # Copy all project files (excluding common build artifacts)
    project_copy_macro = [
        # Use RsyncArgs to exclude unnecessary files
        new_RsyncArgs(
            src=local_project_dir,
            dst=Path(target.default_working_dir),
            excludes=[
                ".venv",
                "__pycache__",
                "*.pyc",
                ".git",
                ".ruff_cache",
                ".pytest_cache",
                "build",
                "dist",
                "*.egg-info",
                ".mypy_cache",
                ".tox",
                ".coverage",
                "htmlcov",
                ".cache",
                "node_modules",
                ".env",
                ".DS_Store",
            ],
        ),
        # Final sync with full project
        "RUN --mount=type=cache,target=/root/.cache/uv uv sync",
    ]

    scripts = []
    if isolate_env:
        scripts += [
            "RANDOM_ID=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)",
            "export UV_PROJECT_ENVIRONMENT=/root/.cache/uv_venv/$RANDOM_ID",
        ]
    else:
        scripts += ["export UV_PROJECT_ENVIRONMENT=/root/.cache/uv_venv/default"]
    if do_sync:
        scripts += ["source $UV_PROJECT_ENVIRONMENT/bin/activate"]

    return EnvComponent(
        installation_macro=[
            await a_macro_install_uv(),
            *dependency_install_macro,
            *project_copy_macro,
        ],
        dependencies=[
            rust_cargo_component,
            base_apt_packages_component,
            ml_nexus_github_credential_component,
        ],
        init_script=[
            f"cd {target.default_working_dir}",
            "source $HOME/.cargo/env",
            "uv self update",
            *scripts,
        ],
        mounts=[],  # No cache mounts for embedded components - everything is in the image
    )


test_a_build_schematics_from_component_uc: IProxy[ContainerSchematic] = (
    a_build_schematics_from_component(
        base_image="ubuntu:20.04",
        components=Injected.list(
            a_project_sync_component(
                tgt=(project := ProjectDef(dirs=[ProjectDir("src", kind="uv")]))
            ),
            a_uv_component(project),
            a_hf_cache_component(),
            base64_runner_component,
        ),
    ).builder.a_build("test_image", use_cache=False)
)


@injected
async def a_component_to_install_requirements_txt(
    storage_resolver: IStorageResolver, logger: "loguru.Logger", /, target: ProjectDef
) -> EnvComponent:
    local_path = await storage_resolver.locate(target.dirs[0].id)
    requirements_txt_path = local_path / "requirements.txt"
    requirements = requirements_txt_path.read_text()
    init_script = []
    packages = [r.split("#")[0].strip() for r in requirements.split("\n")]
    # handle xformers separately
    common_packages = []
    special_packages = []
    for p in packages:
        if "xformers" in p:
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
    return EnvComponent(init_script=init_script)


@injected
async def a_component_to_install_requirements_txt_embedded(
    storage_resolver: IStorageResolver,
    new_RsyncArgs: "NewRsyncArgs",
    logger: "loguru.Logger",
    /,
    target: ProjectDef,
) -> EnvComponent:
    """
    Requirements.txt component with embedded dependencies using multi-stage Docker build.
    This optimizes build caching by separating dependency installation from source code.
    """
    local_path = await storage_resolver.locate(target.dirs[0].id)
    requirements_txt_path = local_path / "requirements.txt"

    # Read and parse requirements
    requirements = requirements_txt_path.read_text()
    packages = [
        r.split("#")[0].strip()
        for r in requirements.split("\n")
        if r.strip() and not r.strip().startswith("#")
    ]

    # Handle xformers and other special packages separately
    common_packages = []
    special_packages = []
    for p in packages:
        if "xformers" in p:
            special_packages.append(p)
        else:
            common_packages.append(p)

    logger.info(f"common packages:{common_packages}")
    logger.info(f"special packages:{special_packages}")

    # Create installation macros for multi-stage build
    dependency_copy_macros = [
        RCopy(
            src=requirements_txt_path,
            dst=Path(target.default_working_dir) / "requirements.txt",
        )
    ]

    # Install dependencies in build stage with cache mount
    common_packages_str = " ".join([f"'{pkg}'" for pkg in common_packages if pkg])
    special_install_lines = "\n".join(
        [f"RUN pip install {p} --no-dependencies" for p in special_packages]
    )

    dependency_install_macro = [
        *dependency_copy_macros,
        f"WORKDIR {target.default_working_dir}",
        f"RUN --mount=type=cache,target=/root/.cache/pip pip install {common_packages_str}"
        if common_packages
        else "",
        special_install_lines if special_packages else "",
    ]
    # Remove empty strings from macro list
    dependency_install_macro = [m for m in dependency_install_macro if m]

    # Copy all project files (excluding common build artifacts)
    project_copy_macro = [
        new_RsyncArgs(
            src=local_path,
            dst=Path(target.default_working_dir),
            excludes=[
                "__pycache__",
                "*.pyc",
                ".git",
                ".ruff_cache",
                ".pytest_cache",
                "build",
                "dist",
                "*.egg-info",
                ".mypy_cache",
                ".tox",
                ".coverage",
                "htmlcov",
                ".cache",
                "node_modules",
                ".env",
                ".DS_Store",
                "venv",
                "env",
                ".venv",
            ],
        )
    ]

    return EnvComponent(
        installation_macro=[*dependency_install_macro, *project_copy_macro],
        init_script=[
            f"cd {target.default_working_dir}",
            "echo 'requirements.txt dependencies pre-installed'",
        ],
    )


class SchematicsUniversal(Protocol):
    async def __call__(
        self,
        target: ProjectDef,
        base_image: Optional[str] = None,
        python_version: Optional[str] = None,
    ) -> ContainerSchematic: ...


@injected
async def schematics_universal(
    a_hf_cache_component: Callable,
    base_apt_packages_component: EnvComponent,
    a_pyenv_component: Callable,
    a_pyenv_component_embedded: Callable,
    base64_runner_component: EnvComponent,
    a_project_sync_component: Callable,
    a_build_schematics_from_component: Callable,
    a_prepare_setup_script_with_deps: Callable,
    a_rye_component: Callable,
    a_uv_component: Callable,
    a_uv_component_embedded: Callable,
    storage_resolver: IStorageResolver,
    ml_nexus_default_base_image: str,
    ml_nexus_default_python_version: str,
    a_get_mount_request_for_pdir: Callable,
    a_component_to_install_requirements_txt: Callable,
    a_component_to_install_requirements_txt_embedded: Callable,
    /,
    target: ProjectDef,
    base_image: Optional[str] = None,
    python_version: Optional[str] = None,
    additional_components: Sequence[EnvComponent] = (),
) -> ContainerSchematic:
    base_image = base_image or ml_nexus_default_base_image
    python_version = python_version or ml_nexus_default_python_version
    setup_script_with_deps: SetupScriptWithDeps = (
        await a_prepare_setup_script_with_deps(target)
    )
    python_components = []
    for dep in setup_script_with_deps.env_deps:
        match dep:
            case "pyvenv":
                python_components.append(
                    await a_pyenv_component(
                        target=target, python_version=python_version
                    )
                )
            case "pyvenv-embedded":
                python_components.append(
                    await a_pyenv_component_embedded(
                        target=target, python_version=python_version
                    )
                )
            case "requirements.txt":
                """
                we need to have a dedicated installer for requirements.txt
                Because xformers cannot be installed without torch!
                We might need a dedicated uv project initialization, instead of using direct requirements.
                That's a TODO for now.
                """
                python_components.append(
                    await a_component_to_install_requirements_txt(target=target)
                )
            case "requirements.txt-embedded":
                python_components.append(
                    await a_component_to_install_requirements_txt_embedded(
                        target=target
                    )
                )
            case "setup.py":
                python_components.append(
                    EnvComponent(
                        init_script=[
                            f"cd {target.default_working_dir}",
                            "pip install -e .",
                        ]
                    )
                )
            case "rye":
                local_project_dir = await storage_resolver.locate(target.dirs[0].id)
                python_components.append(
                    await a_rye_component(
                        project_workdir=target.default_working_dir,
                        local_project_dir=local_project_dir,
                    )
                )
            case "uv":
                python_components.append(await a_uv_component(target=target))
            case "uv-embedded":
                python_components.append(await a_uv_component_embedded(target=target))
            case "poetry":
                raise NotImplementedError("poetry is not supported yet")

    mounts = await asyncio.gather(
        *[
            a_get_mount_request_for_pdir(placement=target.placement, pdir=pdir)
            for pdir in target.yield_project_dirs()
        ]
    )
    setup_component = EnvComponent(dependencies=python_components, mounts=list(mounts))

    components = [
        base64_runner_component,
        base_apt_packages_component,
        await a_hf_cache_component(),
        setup_component,
        await a_project_sync_component(tgt=target),
        *additional_components,
    ]
    return await a_build_schematics_from_component(
        base_image=base_image, components=components
    )


test_build_schematics_universal: IProxy = schematics_universal(
    target=ProjectDef(dirs=[ProjectDir("pinjected_openai", kind="auto")]),
)
test_docker_env: IProxy = injected(DockerEnvFromSchematics)(
    project=ProjectDef(dirs=[ProjectDir("pinjected_openai", kind="auto")]),
    schematics=test_build_schematics_universal,
    docker_host="zeus",
)
test_docker_env_run: IProxy = test_docker_env.run_script("""
ls -lah
""")
test_requirements_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="sketch2lineart", kind="auto", dependencies=[])]
)
test_schematics_req_txt: IProxy = schematics_universal(target=test_requirements_project)
test_req_txt_docker = injected(PersistentDockerEnvFromSchematics)(
    project=test_requirements_project,
    schematics=test_schematics_req_txt,
    docker_host="zeus",
    container_name="test_req_txt_docker",
)
test_req_txt_docker_run: IProxy = test_req_txt_docker.run_script(
    """
ls -lah
"""
)

# Test for auto-embed UV project
test_auto_embed_project: IProxy = ProjectDef(
    dirs=[
        ProjectDir(
            id="test/dummy_projects/test_uv",
            kind="auto-embed",  # This will auto-detect UV and use embedded dependencies
        )
    ]
)

test_schematics_auto_embed: IProxy = schematics_universal(
    target=test_auto_embed_project
)

test_auto_embed_docker: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_auto_embed_project,
    schematics=test_schematics_auto_embed,
    docker_host="zeus",
    container_name="test_auto_embed_docker",
)

test_auto_embed_docker_run: IProxy = test_auto_embed_docker.run_script(
    """
echo "Testing auto-embed UV project"
ls -lah
python --version
uv --version
"""
)

# Test for auto-embed requirements.txt project
test_req_auto_embed_project: IProxy = ProjectDef(
    dirs=[
        ProjectDir(
            id="test/dummy_projects/test_requirements",
            kind="auto-embed",  # This will auto-detect requirements.txt and use embedded dependencies
        )
    ]
)

test_schematics_req_auto_embed: IProxy = schematics_universal(
    target=test_req_auto_embed_project
)

test_req_auto_embed_docker: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_req_auto_embed_project,
    schematics=test_schematics_req_auto_embed,
    docker_host="zeus",
    container_name="test_req_auto_embed_docker",
)

test_req_auto_embed_docker_run: IProxy = test_req_auto_embed_docker.run_script(
    """
echo "Testing auto-embed requirements.txt project"
ls -lah
python --version
pip list
"""
)

# Test for pyvenv-embed project with requirements.txt
test_pyvenv_embed_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_requirements", kind="pyvenv-embed")]
)

test_schematics_pyvenv_embed: IProxy = schematics_universal(
    target=test_pyvenv_embed_project, python_version="3.11"
)

test_pyvenv_embed_docker: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_pyvenv_embed_project,
    schematics=test_schematics_pyvenv_embed,
    docker_host="zeus",
    container_name="test_pyvenv_embed_docker",
)

test_pyvenv_embed_docker_run: IProxy = test_pyvenv_embed_docker.run_script(
    """
echo "Testing pyvenv-embed project"
ls -lah
python --version
pip list
which python
"""
)

# Test for pyvenv-embed project with setup.py
test_pyvenv_embed_setuppy_project: IProxy = ProjectDef(
    dirs=[ProjectDir(id="test/dummy_projects/test_setuppy", kind="pyvenv-embed")]
)

test_schematics_pyvenv_embed_setuppy: IProxy = schematics_universal(
    target=test_pyvenv_embed_setuppy_project, python_version="3.11"
)

test_pyvenv_embed_setuppy_docker: IProxy = injected(PersistentDockerEnvFromSchematics)(
    project=test_pyvenv_embed_setuppy_project,
    schematics=test_schematics_pyvenv_embed_setuppy,
    docker_host="zeus",
    container_name="test_pyvenv_embed_setuppy_docker",
)

test_pyvenv_embed_setuppy_docker_run: IProxy = (
    test_pyvenv_embed_setuppy_docker.run_script(
        """
echo "Testing pyvenv-embed project with setup.py"
ls -lah
python --version
pip list
which python
"""
    )
)

__design__ = load_env_design + design(logger=logger)
