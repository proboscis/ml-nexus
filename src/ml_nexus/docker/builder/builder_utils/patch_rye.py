import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Awaitable, AsyncContextManager

from loguru import logger
from pinjected import injected

from ml_nexus.project_structure import ProjectDir, PlatformDependantPypi
from ml_nexus.rsync_util import RsyncLocation

PatchRyeProject = Callable[[ProjectDir, Path, bool], Awaitable[Path]]


@injected
@asynccontextmanager
async def patch_rye_project(
        storage_resolver,
        new_RsyncArgs,
        /,
        tgt: ProjectDir,
        source_root: Path,
) -> AsyncContextManager[Path]:
    """
     Function: patch_rye_project

     Summary:
     The `patch_rye_project` function carries out the process of preparing a project for launching in the target environment by copying it to a temporary directory and updating specific dependencies in the project's 'pyproject.toml' file.

     Details:

     Parameters:
         - storage_resolver: A service responsible for locating project directories in storage.
         - a_system: A method to perform system-level operations, e.g., file manipulations.
         - tgt (ProjectDir): The project directory in the target environment that is to be patched.
         - source_root (Path): Source root directory.
         - clear (bool, optional): Specify whether to clean the temporary directory. Defaults to False.

     Workflow:
         1. The function first locates the source directory corresponding to the project ID in the storage.
         2. If 'clear' is set to True, the function removes the tmp directory associated with the project ID.
         3. Then it creates a new tmp directory with the project ID.
         4. It syncs the source directory with the newly created tmp directory.
         5. It removes the 'pyproject.toml' file in the tmp directory.
         6. It reads the 'pyproject.toml' from the source directory.
            Dependencies that use the 'file://' protocol are replaced with the corresponding paths in the source root directory.
            The new dependencies are written to a new 'pyproject.toml' file in the tmp directory.
            If a dependency cannot be parsed, it is copied verbatim.

     Returns:
         Path: Returning a Path object that points to the patched project directory in the target environment.

     Note:
         Please make sure to clean the 'tmp' directory, if you found something suspicious because the function won't clear the 'tmp' directory by default.
     """
    # TODO remove requirements.lock
    src = await storage_resolver.locate(tgt.id)
    logger.info(f"not clearing the tmp directory for {tgt.id}. please clean this up if you found something funny.")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        dst = tmp_dir / tgt.id
        rsync = new_RsyncArgs(
            src=RsyncLocation(path=src, host="localhost"),
            dst=RsyncLocation(path=dst),
            excludes=tgt.excludes,
            options=['--delete'],
            hardlink=True
        )
        # await a_system(f"mkdir -p /tmp/{tgt.id}")
        # await a_system(
        #     f"rsync -avH --progress --link-dest={src} {src}/ /tmp/{tgt.id}/ --delete"
        # )
        await rsync.run()
        pyproject_path = dst / "pyproject.toml"
        os.remove(pyproject_path)
        orig_pyproject = Path(src / "pyproject.toml")
        # let's locate dependencies with '@ file://' and replace them with the correct path.
        import toml
        orig_pyproject = toml.loads(orig_pyproject.read_text())
        deps = orig_pyproject['project']['dependencies']
        new_deps = []
        for dep in deps:
            try:
                name, file = dep.split(" @ ")
                if not file.startswith("file://"):
                    new_deps.append(dep)
                    continue
                path = Path(file.replace("file://", ""))
                repo_name = path.name  # repo_name == id
                new_file = f"file://{source_root}/{repo_name}"
                logger.debug(f"replacing {file} with {new_file} in pyproject.toml of {tgt.id}")
                new_deps.append(f"{name} @ {new_file}")

            except Exception as e:
                new_deps.append(dep)

        for ex in tgt.extra_dependencies:
            match ex:
                case PlatformDependantPypi('linux', pkg):
                    new_deps.append(pkg)

        orig_pyproject['project']['dependencies'] = new_deps
        new_pyproject = toml.dumps(orig_pyproject)
        logger.info(f"new toml:\n{new_pyproject}")
        pyproject_path.write_text(new_pyproject)
        yield pyproject_path.parent
