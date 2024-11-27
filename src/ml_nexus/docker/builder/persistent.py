import asyncio
import base64
import uuid
from dataclasses import dataclass
from pathlib import Path

from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.project_structure import IScriptRunner, ProjectDef, ScriptRunContext
from ml_nexus.schematics import ContainerSchematic
from ml_nexus.util import PsResult, CommandException


@dataclass
class PersistentDockerEnvFromSchematics(IScriptRunner):
    _new_DockerEnvFromSchematics: type[DockerEnvFromSchematics]
    _a_system: callable
    _logger: object
    _env_result_download_path: Path

    project: ProjectDef
    schematics: ContainerSchematic
    docker_host: str
    container_name: str

    def __post_init__(self):
        self.container = self._new_DockerEnvFromSchematics(
            project=self.project,
            schematics=self.schematics,
            docker_host=self.docker_host,
            docker_options=["--name", self.container_name]
        )
        self.container_task = None

    async def a_is_container_ready(self):
        try:
            ps: PsResult = await self._a_system(f"docker exec {self.container_name} echo 'hello'")
            return True
        except Exception as e:
            self._logger.info(f"Container {self.container_name} is not ready. {e}")
            return False

    async def ensure_container(self):
        # check if the container is running
        try:
            res: PsResult = await self._a_system(f"ssh {self.docker_host} docker ps | grep {self.container_name}")
            if self.container_name in res.stdout:
                self._logger.info(f"Container {self.container_name} is already running")
                return
        except CommandException as e:
            self._logger.warning(f"Container {self.container_name} is not running. Starting...")
        self.container_task = asyncio.create_task(self.container.run_script(
            "sleep infinity"
        ))

        while not await self.a_is_container_ready():
            await asyncio.sleep(1)
        self._logger.info(f"Container {self.container_name} is ready")

    async def run_script(self, script: str):
        """
        1. ensure the container is running
        2. send base64 encoded script and run it via docker exec
        """
        await self.ensure_container()
        # Now let's build the script and run it.

        init_script = "\n".join(self.schematics.builder.scripts)

        final_script = f"""
{init_script}
{script}
"""
        base64_encoded_script = base64.b64encode(final_script.encode('utf-8')).decode()
        cmd = f"docker exec {self.container_name} bash /usr/local/bin/base64_runner.sh {base64_encoded_script}"
        #await self._a_system(f'ssh {self.docker_host} {cmd}')
        await self._a_system(cmd)

    async def stop(self):
        #await self._a_system(f"ssh {self.docker_host} docker stop {self.container_name}")
        await self._a_system(f"docker stop {self.container_name}")

    async def upload(self, local_path: Path, remote_path: Path):
        await self.ensure_container()
        # ensure path exists
        #await self._a_system(f"ssh {self.docker_host} docker exec {self.container_name} mkdir -p {remote_path.parent}")
        await self._a_system(f"docker exec {self.container_name} mkdir -p {remote_path.parent}")
        # wait, this copies file from the docker_host, hmm..
        await self._a_system(f"docker cp {local_path} {self.container_name}:{remote_path}")

    async def download(self, remote_path: Path, local_path: Path):
        await self.ensure_container()
        await self._a_system(f"docker cp {self.container_name}:{remote_path} {local_path}")

    async def delete(self, remote_path: Path):
        await self.ensure_container()
        #await self._a_system(f"ssh {self.docker_host} docker exec {self.container_name} rm -rf {remote_path}")
        await self._a_system(f"docker exec {self.container_name} rm -rf {remote_path}")

    async def sync_from_container(self, remote_path: Path, local_path: Path):
        await self.ensure_container()
        await self._a_system(f"rsync -avz -e 'docker exec -i' {self.container_name}:{remote_path} {local_path}")

    async def sync_to_container(self, local_path: Path, remote_path: Path):
        await self.ensure_container()
        await self._a_system(f"rsync -avz -e 'docker exec -i' {local_path} {self.container_name}:{remote_path}")

    def random_remote_path(self):
        tmp_name = uuid.uuid4().hex[:8]
        return self.project.placement.resources_root / "tmp" / tmp_name

    def run_context(self) -> ScriptRunContext:
        return ScriptRunContext(
            random_remote_path=self.random_remote_path,
            upload_remote=self.upload,
            delete_remote=self.delete,
            download_remote=self.download,
            local_download_path=self._env_result_download_path,
            env=self
        )
