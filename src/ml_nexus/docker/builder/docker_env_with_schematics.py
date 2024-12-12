import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from ml_nexus.docker_env import DockerHostEnvironment, DockerMount
from ml_nexus.project_structure import IScriptRunner, ProjectDef
from ml_nexus.rsync_util import RsyncLocation
from ml_nexus.schematics import ContainerSchematic, \
    CacheMountRequest, ResolveMountRequest, DirectMountRequest, ContextualMountRequest
from ml_nexus.storage_resolver import IStorageResolver


@dataclass
class DockerHostPlacement:
    """
    Where to place the resources on the docker host
    """
    cache_root: Path
    resource_root: Path
    source_root: Path
    direct_root: Path


@dataclass
class DockerEnvFromSchematics(IScriptRunner):
    _new_DockerHostEnvironment: type[DockerHostEnvironment]
    _a_system: callable
    _storage_resolver: IStorageResolver
    _new_RsyncArgs: callable
    _ml_nexus_default_docker_host_placement: DockerHostPlacement

    project: ProjectDef
    schematics: ContainerSchematic
    docker_host: str
    placement: DockerHostPlacement = None
    pinjected_additional_args: dict[str, str] = field(default_factory=dict)
    docker_options: list[str] = None

    def __post_init__(self):
        if self.placement is None:
            self.placement = self._ml_nexus_default_docker_host_placement

    async def _rsync_mount(self, source, host_dst, mount_point, excludes):
        await self._a_system(f"ssh {self.docker_host} mkdir -p {host_dst}")
        rsync = self._new_RsyncArgs(src=source,
                                    dst=RsyncLocation(
                                        host_dst,
                                        host=self.docker_host
                                    ),
                                    excludes=excludes
                                    )
        await rsync.run()
        return DockerMount(
            source=host_dst,
            target=mount_point
        )

    async def _new_env(self):
        mounts = await self.prepare_mounts()

        return self._new_DockerHostEnvironment(
            project=self.project,
            docker_builder=self.schematics.builder,
            docker_host=self.docker_host,
            additional_mounts=mounts,
            pinjected_additional_args=self.pinjected_additional_args,
            docker_options=self.docker_options
        )

    async def prepare_mounts(self):
        mounts = []
        from pinjected.compatibility.task_group import TaskGroup
        mount_tasks = []

        async def task_impl(cmr: ContextualMountRequest):
            async with cmr.source() as host_src:
                return await self.sync_direct(cmr.excludes, cmr.mount_point, host_src)

        async with TaskGroup() as tg:
            for mount in self.schematics.mount_requests:
                match mount:
                    case CacheMountRequest(name, mount_point):
                        await self._a_system(f"ssh {self.docker_host} mkdir -p {self.placement.cache_root / name}")
                        mounts.append(DockerMount(
                            source=self.placement.cache_root / name,
                            target=mount_point
                        ))
                    case ResolveMountRequest(kind='resource',
                                             resource_id=resource_id,
                                             mount_point=mount_point,
                                             excludes=excludes):
                        local_path = await self._storage_resolver.locate(resource_id)
                        # 1. rsync to remote
                        host_dst = self.placement.resource_root / resource_id

                        mount_task = tg.create_task(self._rsync_mount(local_path, host_dst, mount_point, excludes))
                        # 2. mount
                        mount_tasks.append(mount_task)
                    case ResolveMountRequest(kind='source', resource_id=resource_id,
                                             mount_point=mount_point,
                                             excludes=excludes
                                             ):
                        local_path = await self._storage_resolver.locate(resource_id)
                        host_dst = self.placement.source_root / resource_id
                        mount_task = tg.create_task(self._rsync_mount(local_path, host_dst, mount_point, excludes))
                        mount_tasks.append(mount_task)
                    case ContextualMountRequest() as cmr:
                        mount_tasks.append(tg.create_task(task_impl(cmr)))
                    case DirectMountRequest(source, mount_point, excludes):
                        mount_task = tg.create_task(self.sync_direct(excludes, mount_point, source))
                        mount_tasks.append(mount_task)
                    case _:
                        raise ValueError(f"Invalid mount request {mount}")
        for task in mount_tasks:
            mounts.append(await task)
        return mounts

    async def sync_direct(self, excludes, mount_point, source):
        hash_name = hashlib.sha256(str(source).encode()).hexdigest()[:32]
        host_dst = self.placement.direct_root / hash_name
        return await self._rsync_mount(source, host_dst, mount_point, excludes)

    async def run_script(self, script: str):
        env = (await self._new_env())
        return await env.run_script(script)
