from dataclasses import dataclass, replace, field
from pathlib import Path
from typing import Union, Callable, AsyncContextManager, Awaitable

from ml_nexus.docker.builder.docker_builder import DockerBuilder
from ml_nexus.docker.builder.macros.macro_defs import Macro, _Macro


@dataclass
class CacheMountRequest:
    """to be mounted for persistent cache, like pip's cache"""
    name: str
    mount_point: Path


ResourceID = str


@dataclass
class ResolveMountRequest:
    """to be mounted using storage_resolver, inside container"""
    kind: str
    resource_id: ResourceID
    mount_point: Path
    excludes: list[str] = field(default_factory=list)


@dataclass
class DirectMountRequest:
    """to be mounted directly, inside container"""
    source: Path
    mount_point: Path
    excludes: list[str] = field(default_factory=list)


@dataclass
class ContextualMountRequest:
    """
    This is for sources that generates path just before mounting.
    """
    source: Callable[[], AsyncContextManager[Path]]
    mount_point: Path
    excludes: list[str] = field(default_factory=list)




@dataclass
class ContainerScript:
    script: str


MountRequest = Union[CacheMountRequest, ResolveMountRequest, DirectMountRequest, ContextualMountRequest]
SchematicElement = Union[MountRequest, Macro, ContainerScript]


@dataclass
class ContainerSchematic:
    builder: DockerBuilder
    mount_requests: list[MountRequest]

    def __add__(self, other: Union[SchematicElement, list[SchematicElement]]):
        match other:
            case [*items]:
                res = self
                for item in items:
                    res += item
                return res
            case mount if isinstance(mount, MountRequest):
                return replace(self, mount_requests=self.mount_requests + [mount])
            case macro if isinstance(macro, _Macro):
                return replace(self, builder=self.builder.add_macro(macro))
            case func if isinstance(func, Callable):
                return replace(self, builder=self.builder.add_macro(func))
            case ContainerScript(script):
                return replace(self, builder=self.builder.add_script(script))
            case unk:
                raise ValueError(f"Invalid type {type(unk)}")

    async def a_map_scripts(self, a_func: Callable[[list[str]], Awaitable[list[str]]]):
        replaced = await a_func(self.builder.scripts)
        return replace(self, builder=replace(self.builder, scripts=replaced))