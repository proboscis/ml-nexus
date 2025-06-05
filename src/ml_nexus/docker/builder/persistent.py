import asyncio
import base64
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pinjected import *

from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.project_structure import IScriptRunner, ProjectDef, ScriptRunContext
from ml_nexus.schematics import ContainerSchematic


@injected
async def a_docker_ps(
        logger,
        /,
        docker_host
):
    # ps: PsResult = await a_system(f"ssh {docker_host} \"docker ps -a --format '{{{{json .}}}}'\"")
    ps = await asyncio.subprocess.create_subprocess_shell(
        f"ssh {docker_host} \"docker ps -a --format '{{{{json .}}}}'\"",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await ps.communicate()

    data = [json.loads(line.strip()) for line in stdout.decode().split("\n") if line.strip()]
    df = pd.DataFrame(data)
    df.set_index("Names", inplace=True)
    return df


@dataclass
class PersistentDockerEnvFromSchematics(IScriptRunner):
    _new_DockerEnvFromSchematics: type[DockerEnvFromSchematics]
    _a_system: callable
    _logger: object
    _env_result_download_path: Path
    _a_docker_ps: callable

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
        self.container_wait_lock = asyncio.Lock()

    async def a_is_container_ready(self):
        async with self.container_wait_lock:
            # self._logger.info(f"Checking if container {self.container_name} is ready")
            ps_table = await self._a_docker_ps(docker_host=self.docker_host)
            # self._logger.info(f"ps_table: {ps_table}")
            if self.container_name not in ps_table.index:
                # self._logger.warning(f"Container {self.container_name} not found in ps table")
                return False
            # self._logger.info(f"Container {self.container_name} found in ps table:{ps_table.index}")
            row = ps_table.loc[self.container_name]
            # self._logger.info(f"Container {self.container_name} row: {row}")
            state = row["State"]
            # self._logger.info(f"Container {self.container_name} status: {status}")
            if state == "running":
                return True
            return False

    async def a_wait_container_ready(self):
        while not await self.a_is_container_ready():
            await asyncio.sleep(1)

    async def ensure_container(self):
        # check if the container is running
        if await self.a_is_container_ready():
            self._logger.info(f"Container {self.container_name} is already running")
        else:
            self._logger.warning(f"Container {self.container_name} is not running. Starting...")
            self.container_task = asyncio.create_task(self.container.run_script_without_init(
                "sleep infinity"
            ))
        await self.a_wait_container_ready()
        await self.container.prepare_mounts()  # ensuring source/resource uploads
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
        # await self._a_system(f'ssh {self.docker_host} {cmd}')
        result = await self._a_system(cmd)
        
        if result.exit_code != 0:
            from ml_nexus.util import CommandException
            raise CommandException(
                f"Script execution failed with exit code {result.exit_code}",
                code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr
            )
        return result

    async def stop(self):
        # await self._a_system(f"ssh {self.docker_host} docker stop {self.container_name}")
        await self._a_system(f"docker stop {self.container_name}")

    async def upload(self, local_path: Path, remote_path: Path):
        await self.ensure_container()
        # ensure path exists
        # await self._a_system(f"ssh {self.docker_host} docker exec {self.container_name} mkdir -p {remote_path.parent}")
        await self._a_system(f"docker exec {self.container_name} mkdir -p {remote_path.parent}")
        # wait, this copies file from the docker_host, hmm..
        await self._a_system(f"docker cp {local_path} {self.container_name}:{remote_path}")

    async def download(self, remote_path: Path, local_path: Path):
        await self.ensure_container()
        await self._a_system(f"docker cp {self.container_name}:{remote_path} {local_path}")

    async def delete(self, remote_path: Path):
        await self.ensure_container()
        # await self._a_system(f"ssh {self.docker_host} docker exec {self.container_name} rm -rf {remote_path}")
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
