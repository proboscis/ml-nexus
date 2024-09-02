import abc
import asyncio
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pformat

import yaml
from pinjected import instances, instance, injected
from pydantic import BaseModel
from tqdm import tqdm


class IStorageResolver(ABC):
    @abc.abstractmethod
    async def sync(self):
        pass

    @abc.abstractmethod
    async def locate(self, id: str) -> Path:
        pass

    def __add__(self, other: "IStorageResolver"):
        return CombinedStorageResolver(resolvers=[self, other])

    @staticmethod
    def from_dict(d: dict[str, Path]):
        return StaticStorageResolver(id_to_path=d)

    @staticmethod
    def from_directory(*root_paths: Path):
        return YamlStorageResolver(*root_paths)


class StorageItem(BaseModel):
    id: str


@dataclass
class CombinedStorageResolver(IStorageResolver):
    resolvers: list[IStorageResolver]

    async def sync(self):
        await asyncio.gather(*[r.sync() for r in self.resolvers])

    async def locate(self, id: str) -> Path:
        for resolver in self.resolvers:
            try:
                return await resolver.locate(id)
            except KeyError:
                pass
        raise KeyError(f"could not locate {id}")


class StaticStorageResolver(IStorageResolver):
    """
    A static storage manager that does not sync.
    """

    def __init__(self, id_to_path: dict[str, Path]):
        self.id_to_path = id_to_path

    async def sync(self):
        pass

    async def locate(self, id: str) -> Path:
        return self.id_to_path[id]


@dataclass
class DirectoryStorageResolver(IStorageResolver):
    """
    Treats a directory's subdirectories as storage items.
    """
    root: Path
    id_to_path: dict[str, Path] = field(default_factory=dict)

    def __post_init__(self):
        self.synchronized = False

    async def locate(self, id: str) -> Path:
        if not self.synchronized:
            await self.sync()
            self.synchronized = True
        return self.id_to_path[id]

    async def sync(self):
        for sub_dir in self.root.iterdir():
            if sub_dir.is_dir():
                self.id_to_path[sub_dir.name] = sub_dir.absolute()


class YamlStorageResolver(IStorageResolver):
    """
    Scan the top directory for directories that contain .storage_info.yaml

    """

    def __init__(self, *root_paths: Path):
        self.root_paths = root_paths
        self.id_to_path = {}
        self.synchronized = False

    async def sync(self):
        """
        recursively scan the root_paths, read the .storage_manager.yaml, and register the id_to_path
        :return:
        """
        from loguru import logger
        for root_path in tqdm(self.root_paths, desc="scanning"):
            logger.info(f"scanning {root_path}")
            root_path: Path
            for path in tqdm(root_path.glob("*/.storage_info.yaml"),
                             desc=f"globbing .storage_info.yaml files in {root_path}"):
                info = yaml.load(Path(path).read_text(), Loader=yaml.SafeLoader)
                item = StorageItem.model_validate(info)
                assert isinstance(item, StorageItem)
                self.id_to_path[item.id] = path.parent.absolute()
        logger.info(f"found paths:\n{pformat(self.id_to_path)}")

    async def locate(self, id: str) -> Path:
        if not self.synchronized:
            await self.sync()
            self.synchronized = True
        return self.id_to_path[id]


@instance
async def test_yaml_storage_manager():
    from loguru import logger
    # logger.info(StorageInfo(items=[StorageItem(id="test", path=Path("test"))]).model_dump_json())
    manager = DirectoryStorageResolver(Path("~/repos").expanduser().absolute())
    await manager.sync()
    return manager


@injected
async def local_storage_resolver(
        source_root: Path = Path("~/sources").expanduser().absolute(),
        resource_root: Path = Path("~/resources").expanduser().absolute(),
):
    sources_resolver = DirectoryStorageResolver(source_root)
    resource_resolver = DirectoryStorageResolver(resource_root)
    return sources_resolver + resource_resolver


@injected
async def IdPath(storage_resolver: IStorageResolver, /, id: str) -> Path:
    """
    This, is to be used in place of Path so that the path is resolved by the storage_resolver.
    :param storage_resolver:
    :param id:
    :return:
    """
    return await storage_resolver.locate(id)


__meta_design__ = instances(

)
