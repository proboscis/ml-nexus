import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union

from pinjected import *


@dataclass
class RsyncLocation:
    path: Path
    host: str = field(default="localhost")

    def __post_init__(self):
        self.path = Path(self.path)

    def to_str(self):
        return f"{self.host}:{self.path}" if self.host != "localhost" else str(self.path.expanduser())


@instance
def rsync_semaphore():
    return asyncio.Semaphore(3)


@dataclass
class RsyncArgs:
    _a_system: callable
    _rsync_semaphore: asyncio.Semaphore

    # i want pattern matches to only match except _a_system, but how?
    src: RsyncLocation
    dst: RsyncLocation
    excludes: list[str] = None
    options: list[str] = None
    hardlink: bool = False

    __match_args__ = ('src', 'dst', 'excludes', 'options', 'hardlink')

    def __post_init__(self):
        self.src = self._ensure_loc(self.src)
        self.dst = self._ensure_loc(self.dst)
        if self.hardlink:
            assert self.src.host == self.dst.host, f"hardlinking only works when src and dst are on the same host, but got different hosts.(src:{self.src}, dst:{self.dst})"
        if self.excludes is None:
            self.excludes = []
        if self.options is None:
            self.options = []
        self.excludes = list(set(self.excludes))
        assert isinstance(self.excludes, list), f"excludes is not list, but {type(self.excludes)}"
        assert isinstance(self.options, list), f"options is not list, but {type(self.options)}"

    def _ensure_loc(self, tgt: Union[RsyncLocation, Path, str]):
        match tgt:
            case RsyncLocation():
                return tgt
            case Path():
                return RsyncLocation(tgt)
            case str() if ":" in tgt:
                host, path = tgt.split(":")
                return RsyncLocation(Path(path), host)
            case str():
                return RsyncLocation(Path(tgt))
            case _:
                raise ValueError(f"unexpected type {type(tgt)}")

    async def run(self):
        async with self._rsync_semaphore:
            args = self
            excludes = args.excludes
            options = args.options
            cmd = f"rsync -avH "
            if self.hardlink:
                cmd += f"--link-dest={args.src.to_str()} "

            cmd += f"{self.src.to_str()}/ {self.dst.to_str()}/"
            if options:
                cmd += " " + " ".join(options)
            with to_filter_file(excludes) as filter_file:
                cmd += f" --filter='merge {filter_file}'"
                # logger.debug(f"rsync with cmd: {cmd}")#, filterfile:\n{filter_file.read_text()}")
                await self._a_system(cmd)
        # result_ls = await self._a_system(f"ls -la {self.dst.to_str()}")
        # logger.info(f"rsync result dst ls:{result_ls}")

@dataclass
class NewRsyncArgs:
    # just a stub for type alias
    def __call__(self,
                 src: RsyncLocation,
                 dst: RsyncLocation,
                 excludes: list[str] = None,
                 options: list[str] = None,
                 hardlink: bool = False
                 )->RsyncArgs:
        pass

@contextmanager
def to_filter_file(excludes):
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        filter_file = tmpdir / "filter.txt"
        filter = ""
        for ex in excludes:
            filter += f"- {ex}\n"
        filter_file.write_text(filter)
        yield filter_file
