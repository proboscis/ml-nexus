import asyncio
import base64
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from pinjected import *
from pinjected.compatibility.task_group import TaskGroup

from ml_nexus.docker.builder.docker_builder import DockerBuilder
from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.project_structure import (
    ProjectDef,
    ProjectDir,
    ProjectPlacement,
    IScriptRunner,
    ScriptRunContext,
)
from ml_nexus.rsync_util import RsyncArgs, RsyncLocation
from ml_nexus.storage_resolver import IStorageResolver
from ml_nexus.util import CommandException


@injected
async def a_ssh_cmd(logger, a_system, /, host, cmd: str):
    async def attempt():
        return await a_system(f"ssh {host} {cmd}")

    while True:
        try:
            return await attempt()
        except CommandException as ce:
            if (
                "Connection reset by peer" in ce.stderr
                or "Connection closed by remote host" in ce.stderr
            ):
                logger.info(f"ssh command failed with {ce.stderr}. Retrying...")
                continue
            else:
                raise ce


@dataclass
class DockerMount:
    # a path of a host to be mounted on docker
    source: Path
    # a path of a docker to mount the source
    target: Path


@dataclass
class DockerHostMounter:
    """
    Currently rsync all resources and mounts it on /resources
    """

    _storage_resolver: IStorageResolver
    _a_system: Callable
    _a_ssh_cmd: Callable
    _new_RsyncArgs: type

    host_resource_root: Path

    async def rsync_ids_to_root(self, host, tgts: list[ProjectDir]):
        root_path = self.host_resource_root

        async def task(dir: ProjectDir):
            source_path: Path = await self._storage_resolver.locate(dir.id)
            # await self._a_system(f"ssh {host} mkdir -p {root_path / dir.id}/")
            await self._a_ssh_cmd(host, f"mkdir -p {root_path / dir.id}/")
            rsync: RsyncArgs = self._new_RsyncArgs(
                src=source_path,
                dst=RsyncLocation(host=host, path=root_path / dir.id),
                excludes=dir.excludes,
                options=["--delete"],
            )
            await rsync.run()

        async with TaskGroup() as tg:
            for pdir in tgts:
                if pdir.kind == "resource":
                    tg.create_task(task(pdir))

    async def prepare_resource(self, host, tgt: ProjectDef):
        await self.rsync_ids_to_root(host, list(tgt.yield_project_dirs()))

    def docker_opts(self, placement: ProjectPlacement):
        return f"-v {self.host_resource_root}:{placement.resources_root}"


@dataclass
class DockerHostEnvironment(IScriptRunner):
    _a_system: Callable
    _a_system_parallel: Callable
    _storage_resolver: IStorageResolver
    _new_RsyncArgs: type
    _macro_install_base64_runner: Macro
    _logger: object
    _env_result_download_path: Path
    _ml_nexus_default_docker_image_repo: str
    _ml_nexus_default_docker_host_mounter: DockerHostMounter

    project: ProjectDef
    docker_builder: DockerBuilder
    docker_host: str

    _ml_nexus_docker_build_context: Optional[str] = None

    mounter: Optional[DockerHostMounter] = None
    image_tag: Optional[str] = None
    additional_mounts: list[DockerMount] = None
    docker_options: list[str] = None
    shared_memory_size: str = "10g"
    network: str = "host"
    pinjected_additional_args: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.image_tag is None:
            lower_id = self.project.dirs[0].id.lower()
            self.image_tag = f"{self._ml_nexus_default_docker_image_repo}/{lower_id}"
        self.docker_builder = self.docker_builder.add_macro(
            self._macro_install_base64_runner
        ).add_macro(
            [
                f"ENV HF_HOME={self.project.placement.resources_root / 'huggingface'}",
            ]
        )
        if self.mounter is None:
            self.mounter = self._ml_nexus_default_docker_host_mounter

        self.sync_lock = asyncio.Lock()
        self.synced = asyncio.Event()

    async def prepare(self):
        async with self.sync_lock:
            if self.synced.is_set():
                return self.image_tag
            else:
                image = await self.docker_builder.a_build(
                    self.image_tag, use_cache=True
                )
                # No pushing required, since it's building locally.
                await self.mounter.prepare_resource(self.docker_host, self.project)

                return image

    async def build_docker_cmd(self, cmd: str):
        image = await self.prepare()
        volume_options = f""
        if self.additional_mounts is not None:
            for mount in self.additional_mounts:
                volume_options += f" -v {mount.source}:{mount.target}"
        if self.docker_options is not None:
            opts = " ".join(self.docker_options)
        else:
            opts = ""

        # Get docker command with context if specified
        docker_base = "docker"
        if self._ml_nexus_docker_build_context:
            docker_base = f"docker --context {self._ml_nexus_docker_build_context}"

        docker_cmd = f"{docker_base} run --gpus all --net={self.network} {self.mounter.docker_opts(self.project.placement)} {volume_options} {opts} --shm-size={self.shared_memory_size} --rm {image} {cmd}"
        return docker_cmd

    async def run_script(self, script: str) -> "PsResult":
        # init_script = await self.docker_builder.a_entrypoint_script()
        init_script = "\n".join(self.docker_builder.scripts)

        final_script = f"""
{init_script}
{script}
"""
        base64_encoded_script = base64.b64encode(final_script.encode("utf-8")).decode()
        cmd = await self.build_docker_cmd(
            f"bash /usr/local/bin/base64_runner.sh {base64_encoded_script}"
        )
        result = await self._a_system_parallel(f"ssh {self.docker_host} {cmd}")

        if result.exit_code != 0:
            from ml_nexus.util import CommandException

            raise CommandException(
                f"Script execution failed with exit code {result.exit_code}",
                code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result

    async def run_script_without_init(self, script: str) -> "PsResult":
        base64_encoded_script = base64.b64encode(script.encode("utf-8")).decode()
        cmd = await self.build_docker_cmd(
            f"bash /usr/local/bin/base64_runner.sh {base64_encoded_script}"
        )
        result = await self._a_system_parallel(f"ssh {self.docker_host} {cmd}")

        if result.exit_code != 0:
            from ml_nexus.util import CommandException

            raise CommandException(
                f"Script execution failed with exit code {result.exit_code}",
                code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        return result

    def container_path_to_host_path(self, path):
        return Path(
            str(path).replace(
                str(self.project.placement.resources_root),
                str(self.mounter.host_resource_root),
                1,
            )
        )

    async def upload_remote(self, local: Path, remote: Path):
        remote = self.container_path_to_host_path(remote)
        if not local.is_dir():
            await self._a_system(f"ssh {self.docker_host} mkdir -p {remote.parent}")
            await self._a_system(f"scp -r {local} {self.docker_host}:{remote}")
        else:
            await self._a_system(f"ssh {self.docker_host} mkdir -p {remote}")
            rsync: RsyncArgs = self._new_RsyncArgs(
                src=local,
                dst=RsyncLocation(host=self.docker_host, path=remote),
                excludes=[],
                options=[],
            )
            await rsync.run()

    async def delete_remote(self, remote: Path):
        remote = self.container_path_to_host_path(remote)
        await self._a_system(f"ssh {self.docker_host} rm -rf {remote}")

    async def download_remote(self, remote: Path, local: Path):
        remote = self.container_path_to_host_path(remote)
        await self._a_system(f"scp -r {self.docker_host}:{remote} {local}")

    def random_remote_path(self):
        tmp_name = uuid.uuid4().hex[:8]
        return self.project.placement.resources_root / "tmp" / tmp_name
        # return self.mounter.host_resource_root / "tmp" / tmp_name

    def run_context(self) -> ScriptRunContext:
        return ScriptRunContext(
            random_remote_path=self.random_remote_path,
            upload_remote=self.upload_remote,
            delete_remote=self.delete_remote,
            download_remote=self.download_remote,
            local_download_path=self._env_result_download_path,
            env=self,
        )


default_ignore_set = [
    ".git",
    ".venv",
    ".idea",
    "__pycache__",
    ".pyc",
    ".idea",
    ".log",
    "src/wandb",
    "*.pth",
    "*.pkl",
    "*.tar.gz",
    "venv",
    "*.mdb",
    "vscode-plugin",
]
