from __future__ import annotations

import asyncio
import base64
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Union

from google.cloud import aiplatform
from google.auth.credentials import Credentials

from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.project_structure import IScriptRunner, ProjectDef, ScriptRunContext
from ml_nexus.schematics import ContainerSchematic
from ml_nexus.util import PsResult, CommandException


@dataclass
class VertexAICustomJobFromSchematics(IScriptRunner):
    _macro_install_base64_runner: Macro
    _a_docker_push: Callable

    project: ProjectDef
    schematics: ContainerSchematic
    machine_config: dict
    project_id: str
    location: str
    service_account: Optional[str] = None
    credentials_provider: Optional[Callable[[], Optional[Credentials]]] = None
    docker_image_tag: Optional[str] = None
    stream_log: bool = True
    pinjected_additional_args: Optional[dict[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        if self.docker_image_tag is None:
            random_hash = uuid.uuid4().hex[:8]
            base = self.machine_config.get("image_registry", "us-central1-docker.pkg.dev")
            repo = self.machine_config.get("image_repo", "vertex-built")
            name = self.project.dirs[0].id.lower()
            self.docker_image_tag = f"{base}/{self.project_id}/{repo}/{name}:{random_hash}"

        self.schematics += [
            self._macro_install_base64_runner,
            f"WORKDIR {self.project.default_working_dir}",
        ]

    def _prepare_script(self, script: str) -> str:
        init_script = "\n".join(self.schematics.builder.scripts)
        full_script = f"{init_script}\n{script}"
        b64 = base64.b64encode(full_script.encode("utf-8")).decode()
        return "bash /usr/local/bin/base64_runner.sh " + b64

    async def _prepare_impl(self) -> str:
        tag = await self.schematics.builder.a_build(self.docker_image_tag)
        await self._a_docker_push(tag)
        return tag

    async def prepare(self) -> str:
        if not hasattr(self, "_prepare_future") or self._prepare_future is None:
            self._prepare_future = asyncio.create_task(self._prepare_impl())
        return await self._prepare_future

    def _make_credentials(self) -> Optional[Credentials]:
        if self.credentials_provider is not None:
            return self.credentials_provider()
        return None

    def _aiplatform_init(self):
        creds = self._make_credentials()
        aiplatform.init(project=self.project_id, location=self.location, credentials=creds)

    def _build_worker_pool_specs(self, cmd: str) -> list[dict]:
        machine_type = self.machine_config.get("machine_type", "n1-standard-4")
        accelerator_type = self.machine_config.get("accelerator_type")
        accelerator_count = self.machine_config.get("accelerator_count")
        boot_disk_type = self.machine_config.get("boot_disk_type", "pd-ssd")
        boot_disk_size_gb = self.machine_config.get("boot_disk_size_gb", 100)

        machine_spec = {"machine_type": machine_type}
        if accelerator_type and accelerator_count:
            machine_spec["accelerator_type"] = accelerator_type
            machine_spec["accelerator_count"] = accelerator_count

        container_spec = {
            "image_uri": self.image,
            "command": ["bash", "-lc"],
            "args": [cmd],
        }

        pool = {
            "machine_spec": machine_spec,
            "replica_count": 1,
            "disk_spec": {
                "boot_disk_type": boot_disk_type,
                "boot_disk_size_gb": boot_disk_size_gb,
            },
            "container_spec": container_spec,
        }
        return [pool]

    def _submit_job(self, cmd: str):
        self._aiplatform_init()
        display_name = self.machine_config.get("job_name") or f"mlnexus-{uuid.uuid4().hex[:8]}"
        worker_pool_specs = self._build_worker_pool_specs(cmd)
        custom_job = aiplatform.CustomJob(
            display_name=display_name,
            worker_pool_specs=worker_pool_specs,
            staging_bucket=self.machine_config.get("staging_bucket"),
            service_account=self.service_account or self.machine_config.get("service_account"),
            network=self.machine_config.get("network"),
            labels=self.machine_config.get("labels"),
        )
        custom_job.run(sync=True)
        return custom_job

    def _determine_exit_code(self, state: Union[str, int, None]) -> int:
        if state in ("JOB_STATE_SUCCEEDED", 1):
            return 0
        if state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED", "JOB_STATE_UNSPECIFIED", 2, 3, 4, 0, None):
            return 1
        return 1

    async def run_script(self, script: str, delete_after_completion: bool = True) -> PsResult:
        self.image = await self.prepare()
        cmd = self._prepare_script(script)
        try:
            job = await asyncio.to_thread(self._submit_job, cmd)
            state = getattr(job, "state", None)
            exit_code = self._determine_exit_code(state)
            stdout = ""
            stderr = ""
            if exit_code != 0:
                raise CommandException(
                    message=f"Command failed with exit code {exit_code}",
                    code=exit_code,
                    stdout=stdout,
                    stderr=stderr,
                )
            return PsResult(stdout=stdout, stderr=stderr, exit_code=exit_code)
        except Exception as e:
            raise CommandException(
                message=f"Error executing command: {e!s}",
                code=1,
                stdout="",
                stderr=str(e),
            )

    def run_context(self) -> ScriptRunContext:
        def _random_remote_path() -> Path:
            return Path("/tmp") / f"mlnexus-{uuid.uuid4().hex[:8]}"

        async def _upload_remote(local: Path, remote: Path):
            raise NotImplementedError("upload_remote is not supported in VertexAICustomJobFromSchematics run_context")

        async def _delete_remote(path: Path):
            return None

        async def _download_remote(remote: Path, local: Path):
            raise NotImplementedError("download_remote is not supported in VertexAICustomJobFromSchematics run_context")

        return ScriptRunContext(
            random_remote_path=_random_remote_path,
            upload_remote=_upload_remote,
            delete_remote=_delete_remote,
            download_remote=_download_remote,
            local_download_path=Path.cwd(),
            env=self,
            preparation=self.prepare,
        )
