"""
Fileベースで変換作業を行うせいで、tempfileが避けられない。
in-memoryでどうにかできると嬉しいのだが、、

"""

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from pinjected import *

from ml_nexus.project_structure import ProjectDir, ProjectPlacement
from ml_nexus.rsync_util import RsyncLocation


@injected
@asynccontextmanager
async def patch_uv_dir(
    new_RsyncArgs,
    storage_resolver,
    logger,
    /,
    tgt: ProjectDir,
    placement: ProjectPlacement,
):
    """
        This somehow breaks the toml. and uv fails to parse the toml!
        we need to swap
        Original tool.uv is :

        ```
    [tool.uv]
    conflicts = [
        [{ extra = "cpu" }, { extra = "cu124" }],
    ]
    ```
        but after the patch, it becomes:
    ```
    [tool.uv]
    conflicts = [ [ [ "extra",], [ "extra",],],]

    ```

    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        src = await storage_resolver.locate(tgt.id)
        tmp_dir = Path(tmp_dir)
        dst = tmp_dir / tgt.id
        rsync = new_RsyncArgs(
            src=RsyncLocation(path=src, host="localhost"),
            dst=RsyncLocation(path=dst),
            excludes=tgt.excludes,
            options=["--delete"],
            hardlink=True,
        )
        await rsync.run()
        pyproject_path = dst / "pyproject.toml"
        os.remove(pyproject_path)
        orig_pyproject = Path(src / "pyproject.toml")
        # let's locate dependencies with '@ file://' and replace them with the correct path.
        import tomlkit

        orig_pyproject = tomlkit.loads(orig_pyproject.read_text())
        deps = orig_pyproject["project"]["dependencies"]
        new_deps = []
        for dep in deps:
            try:
                name, file = dep.split(" @ ")
                if not file.startswith("file://"):
                    new_deps.append(dep)
                    continue
                path = Path(file.replace("file://", ""))
                repo_name = path.name  # repo_name == id
                new_file = f"file://{placement.sources_root}/{repo_name}"
                logger.debug(
                    f"replacing {file} with {new_file} in pyproject.toml of {tgt.id}"
                )
                new_deps.append(f"{name} @ {new_file}")
            except Exception:
                new_deps.append(dep)

        orig_pyproject["project"]["dependencies"] = new_deps
        new_pyproject = tomlkit.dumps(orig_pyproject)
        logger.info(f"new toml:\n{new_pyproject}")
        pyproject_path.write_text(new_pyproject)
        yield pyproject_path.parent
