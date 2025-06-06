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


def _create_storage_error_message(
    resolver_type: str,
    requested_id: str,
    available_ids: list[str],
    resolver_info: dict[str, str] | None = None,
) -> str:
    """Create a detailed error message for storage resolution failures."""
    available_str = "\n  ".join(sorted(available_ids)[:20])
    if len(available_ids) > 20:
        available_str += f"\n  ... and {len(available_ids) - 20} more"

    message = f"""
StorageResolver Error: Cannot locate project/resource with ID '{requested_id}'

Resolver Type: {resolver_type}
{f"Resolver Info: {resolver_info}" if resolver_info else ""}

Available IDs ({len(available_ids)}):
  {available_str if available_ids else "No IDs available - resolver may not be synced or directories may be empty"}

How to fix this issue:

1. Check if the ID exists in your configured directories
2. Ensure the storage resolver is properly configured

Configuration options:

a) Configure source/resource roots in your __pinjected__.py:
   ```python
   from pathlib import Path
   from pinjected import design
   from ml_nexus import load_env_design
   
   __design__ = load_env_design + design(
       ml_nexus_source_root=Path("~/my_sources").expanduser(),
       ml_nexus_resource_root=Path("~/my_resources").expanduser(),
   )
   ```

b) Or override the entire storage resolver:
   ```python
   from ml_nexus.storage_resolver import StaticStorageResolver, DirectoryStorageResolver
   
   my_resolver = StaticStorageResolver({{
       "{requested_id}": Path("/path/to/{requested_id}"),
       # Add more mappings...
   }})
   
   __design__ = load_env_design + design(
       storage_resolver=my_resolver
   )
   ```

c) For testing, use StaticStorageResolver:
   ```python
   test_resolver = StaticStorageResolver({{
       "test_project": Path("/test/path"),
   }})
   ```

See documentation: doc/storage_resolver_architecture.md
"""
    return message


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

    def _collect_resolver_info(self) -> tuple[list[str], dict[str, str]]:
        """Collect available IDs and resolver information for error reporting."""
        all_available_ids = []
        resolver_infos = []

        for resolver in self.resolvers:
            if hasattr(resolver, "id_to_path"):
                all_available_ids.extend(resolver.id_to_path.keys())

            resolver_type = type(resolver).__name__
            if hasattr(resolver, "__class__"):
                # This will be checked after the class definitions
                resolver_infos.append(resolver_type)

        return all_available_ids, {"Combined resolvers": ", ".join(resolver_infos)}

    async def locate(self, id: str) -> Path:
        for resolver in self.resolvers:
            try:
                return await resolver.locate(id)
            except KeyError:
                pass

        all_available_ids, resolver_info = self._collect_resolver_info()
        raise KeyError(
            _create_storage_error_message(
                "CombinedStorageResolver", id, all_available_ids, resolver_info
            )
        )


class StaticStorageResolver(IStorageResolver):
    """
    A static storage manager that does not sync.
    """

    def __init__(self, id_to_path: dict[str, Path]):
        self.id_to_path = id_to_path

    async def sync(self):
        pass

    async def locate(self, id: str) -> Path:
        if id in self.id_to_path:
            return self.id_to_path[id]

        raise KeyError(
            _create_storage_error_message(
                "StaticStorageResolver",
                id,
                list(self.id_to_path.keys()),
                {"Static mappings": f"{len(self.id_to_path)} entries"},
            )
        )


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

        if id in self.id_to_path:
            return self.id_to_path[id]

        raise KeyError(
            _create_storage_error_message(
                "DirectoryStorageResolver",
                id,
                list(self.id_to_path.keys()),
                {"Root directory": str(self.root)},
            )
        )

    async def sync(self):
        for sub_dir in tqdm(self.root.iterdir(), f"scanning {self.root}"):
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
            for path in tqdm(
                root_path.glob("*/.storage_info.yaml"),
                desc=f"globbing .storage_info.yaml files in {root_path}",
            ):
                info = yaml.load(Path(path).read_text(), Loader=yaml.SafeLoader)
                item = StorageItem.model_validate(info)
                assert isinstance(item, StorageItem)
                self.id_to_path[item.id] = path.parent.absolute()
        logger.info(f"found paths:\n{pformat(self.id_to_path)}")

    async def locate(self, id: str) -> Path:
        if not self.synchronized:
            await self.sync()
            self.synchronized = True

        if id in self.id_to_path:
            return self.id_to_path[id]

        root_paths_str = ", ".join(str(p) for p in self.root_paths)
        raise KeyError(
            _create_storage_error_message(
                "YamlStorageResolver",
                id,
                list(self.id_to_path.keys()),
                {
                    "Root paths": root_paths_str,
                    "Note": "Looks for .storage_info.yaml files",
                },
            )
        )


@instance
async def test_yaml_storage_manager():
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


__design__ = instances()
