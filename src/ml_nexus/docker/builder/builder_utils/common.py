import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import toml
from pinjected import injected
from pinjected.compatibility.task_group import TaskGroup

from ml_nexus.docker.builder.macros.macro_defs import Macro
from ml_nexus.project_structure import ProjectDef
from returns.result import safe, ResultE, Failure, Success


@safe
def maybe_read_file(p: Path) -> ResultE:
    return p.read_text()


def attr_toml(key):
    @safe
    def impl(text):
        data = toml.loads(text)
        return data[key]

    return impl


@injected
async def a_infer_source_kind(path: Path):
    pyproject = maybe_read_file(path / "pyproject.toml")
    tool_rye = pyproject.map(attr_toml("tool.rye"))
    requirements_txt = maybe_read_file(path / "requirements.txt")

    match (pyproject, tool_rye, requirements_txt):
        case (Success(_), Success(_), _):
            return "rye"
        case (Success(_), Failure(), _):
            return 'uv'
        case (Failure(), _, Success(_)):
            return 'source'
        case (Failure(), Failure(), Failure()):
            return 'resource'


@injected
async def gather_rsync_macros_project_def(
        storage_resolver,
        patch_rye_project,
        patch_uv_dir,
        RsyncArgs,
        a_infer_source_kind,
        logger,
        /,
        pro: ProjectDef) -> list[Macro]:
    res = []
    async with TaskGroup() as tg:
        async def task(pdir):
            kind = await a_infer_source_kind(pdir.path) if pdir.kind == "auto" else pdir.kind
            if kind == "source":
                local_path = await storage_resolver.locate(pdir.id)
                return RsyncArgs(src=local_path, dst=Path('/sources') / pdir.id, excludes=pdir.excludes)
            elif kind == "uv":
                @asynccontextmanager
                async def macro_impl(cxt):
                    async with patch_uv_dir(tgt=pdir, placement=pro.placement) as patched_path:
                        yield [
                            f"#Copy patched uv project:{pdir.id}",
                            RsyncArgs(src=patched_path, dst=pro.placement.sources_root / pdir.id,
                                      excludes=pdir.excludes)
                        ]

                return macro_impl
            elif kind == "rye":
                @asynccontextmanager
                async def macro_impl(cxt):
                    # this is to prevent patching to run before building.
                    async with patch_rye_project(tgt=pdir, source_root=pro.placement.sources_root) as patched_path:
                        yield [
                            f"#Copy patched rye project:{pdir.id}",
                            RsyncArgs(src=patched_path, dst=pro.placement.sources_root / pdir.id,
                                      excludes=pdir.excludes)
                        ]

                return macro_impl
            elif kind == "setup.py":
                local_path = await storage_resolver.locate(pdir.id)
                return RsyncArgs(src=local_path, dst=Path('/sources') / pdir.id, excludes=pdir.excludes)
            elif kind == 'resource':
                logger.info(f"resource is to be mounted so not included in the container.")
            else:
                raise ValueError(f"unknown kind {kind} for pdir {pdir.id}")

        for pdir in pro.yield_project_dirs():
            res.append(tg.create_task(task(pdir)))
    return [a for a in list(await asyncio.gather(*res)) if a is not None]
