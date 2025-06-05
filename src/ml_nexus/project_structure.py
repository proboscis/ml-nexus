import abc
import uuid
from abc import ABC
from dataclasses import dataclass, field, replace
from itertools import chain
from pathlib import Path
from typing import Optional, Callable, Awaitable, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from ml_nexus.util import PsResult
from pinjected.compatibility.task_group import TaskGroup
import pandas as pd


@dataclass
class ProjectDir:
    id: str
    kind: Literal['source', 'resource', 'auto', 'rye', 'uv', 'setup.py'] = 'auto'
    dependencies: list["ProjectDir"] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    extra_dependencies: list["PlatformDependantPypi"] = field(default_factory=list)

    def project_dirs(self):
        for dep in self.dependencies:
            yield from dep.project_dirs()
        yield self


@dataclass(frozen=True)
class ProjectPlacement:
    """
    a class to hold policy for placing sources and resources
    """
    sources_root: Path
    resources_root: Path


DEFAULT_PLACEMENT = ProjectPlacement(
    sources_root=Path("/sources"),
    resources_root=Path("/resources"),
)


@dataclass
class PlatformDependantPypi:
    system: str
    package: str


@dataclass
class ProjectDef:
    dirs: list[ProjectDir]
    placement: ProjectPlacement = DEFAULT_PLACEMENT
    default_working_dir: Optional[Path] = None

    def __post_init__(self):
        if not self.dirs:
            self.default_working_dir = Path("/")
        if self.default_working_dir is None:
            self.default_working_dir = self.placement.sources_root / self.dirs[0].id

    def yield_project_dirs(self):
        for dir in self.dirs:
            yield from dir.project_dirs()

    @property
    def extra_dependencies(self) -> list[PlatformDependantPypi]:
        extras = list(chain(*[d.extra_dependencies for d in self.yield_project_dirs()]))
        return extras


# the basic structure
# IEnvironmentFactory -> IRunner

@dataclass
class ScriptRunResult:
    run_id: str
    result_path: Path


class IRunner(ABC):

    @abc.abstractmethod
    async def run(self, command: str):
        pass


@dataclass
class ScriptRunContext:
    random_remote_path: Callable[[], Path]
    upload_remote: Callable[[Path, Path], Awaitable]
    delete_remote: Callable[[Path], Awaitable]
    download_remote: Callable[[Path, Path], Awaitable]
    local_download_path: Path
    env: 'IScriptRunner'

    preparation: Optional[Callable[[], Awaitable]] = None
    _upload_mapping: dict[Path, Path] = field(default_factory=dict)

    @property
    def upload_mapping(self) -> dict[Path, Path]:
        return self._upload_mapping

    def with_upload(self,
                    *local_paths,
                    uploads: dict[Path, Path] = None
                    ) -> 'ScriptRunContext':
        def parse(p):
            match p:
                case str():
                    return [Path(p)]
                case Path():
                    return [p]
                case [*items]:
                    res = []
                    for i in items:
                        res.extend(parse(i))
                    return res
                case _:
                    raise ValueError(f"invalid type {type(p)}")

        local_paths = parse(local_paths)
        mapping = dict()
        mapped = []
        for local in local_paths:
            tmp_name = uuid.uuid4().hex[:8]
            if not local.is_dir():
                tmp_name += local.suffix
            dest = self.random_remote_path() / tmp_name
            mapping[local] = dest
            mapped.append(dest)

        for local, remote in (uploads or {}).items():
            mapping[local] = remote
            mapped.append(remote)

        return replace(
            self,
            _upload_mapping=self.upload_mapping | mapping
        )

    async def run_script(self, script: str) -> ScriptRunResult:
        if self.preparation is not None:
            await self.preparation()
        run_time = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")
        run_id = run_time + "-" + uuid.uuid4().hex[:6]
        result_dir = self.random_remote_path()
        async with TaskGroup() as tg:
            for local, remote in self.upload_mapping.items():
                tg.create_task(self.upload_remote(local, remote))

        upload_envs = "\n".join([
            f"export UPLOAD_{i}={remote}"
            for i, remote in enumerate(self.upload_mapping.values())
        ])

        set_result_env = f"""
mkdir -p {result_dir}
export RUN_RESULT_DIR={result_dir}
{upload_envs}
"""
        script = set_result_env + script
        await self.env.run_script(script)

        download_dst = self.local_download_path / run_id
        download_dst.parent.mkdir(parents=True, exist_ok=True)
        await self.download_remote(result_dir, download_dst)
        async with TaskGroup() as tg:
            for remote in self.upload_mapping.values():
                tg.create_task(self.delete_remote(remote))
            tg.create_task(self.delete_remote(result_dir))
        return ScriptRunResult(
            run_id=run_id,
            result_path=download_dst
        )


class IScriptRunner(IRunner):

    def run_context(self) -> ScriptRunContext:
        raise NotImplementedError()

    @abc.abstractmethod
    async def run_script(self, script: str) -> 'PsResult':
        pass

    async def run(self, command: str):
        return await self.run_script(command)
