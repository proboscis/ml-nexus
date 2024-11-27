from dataclasses import dataclass
from pathlib import Path
from typing import Union, Callable, Awaitable

from ml_nexus.rsync_util import RsyncArgs


@dataclass
class Block:
    code: str


@dataclass
class RCopy:
    src: Path
    dst: Path


@dataclass
class BuildMacroContext:
    build_dir: Path


PureMacro = Union[str, Block, RCopy, RsyncArgs, list["Macro"]]
CodeBuilder = Callable[[BuildMacroContext], Awaitable[PureMacro]]
_Macro = str | Block | RCopy | RsyncArgs
_MacroImpl = _Macro | CodeBuilder
Macro = _MacroImpl | list[_MacroImpl]


