import asyncio
import inspect
import os
import shlex
from contextlib import asynccontextmanager
from hashlib import md5

from pinjected.compatibility.task_group import TaskGroup
from dataclasses import replace
from pathlib import Path
from pprint import pformat
from tempfile import TemporaryDirectory
from typing import Union

from loguru import logger
from pinjected import *

from ml_nexus.assertions import is_async_context_manager
from ml_nexus import load_env_design
from ml_nexus.docker.asyncio_lock import KeyedLock
from ml_nexus.docker.builder.builder_utils.docker_contexts import a_docker_push__local
from ml_nexus.docker.builder.macros.macro_defs import Block, RCopy, BuildMacroContext, Macro
from ml_nexus.path_util import path_hash
from ml_nexus.rsync_util import RsyncArgs, RsyncLocation


@injected
async def build_image_with_copy(
        a_system,
        /,
        from_image,
        pre_copy_commands,
        post_copy_commands,
        docker_resource_paths: dict[Path, Path],
        tag,
        push=False
):
    # make a tmp dir,
    # copy the dockerfile
    # make a hardlink to the resources
    # build the image
    # copy the dockerfile
    copy_commands = ""
    for src, dst in docker_resource_paths.items():
        copy_commands += f"COPY {path_hash(dst)} {dst}\n"
    dockerfile = f"""
FROM {from_image}
{pre_copy_commands}
{copy_commands}
{post_copy_commands}
"""

    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        dockerfile_path = tmpdir / "Dockerfile"
        dockerfile_path.write_text(dockerfile)

        for src, dst in docker_resource_paths.items():
            await a_system(
                f"rsync -avH --progress --link-dest={src.expanduser()} {src.expanduser()}/ {tmpdir / path_hash(dst)}/")

        await a_system(f"docker build -t {tag} {tmpdir}")
        if push:
            await a_system(f"docker push {tag}")
        return tag


def get_large_files(directory, size_threshold):
    large_files = []

    # Recursively walk through the directory
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            try:
                filesize = os.path.getsize(filepath)
                # Check if the file size is above the threshold
                if filesize >= size_threshold:
                    large_files.append((Path(filepath), filesize))
            except OSError as e:
                print(f"Error accessing file {filepath}: {e}")

    return large_files


def format_size(bytes):
    # Convert bytes to a human-readable format
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.2f} {unit}"
        bytes /= 1024


def log_large_files(directory, size_threshold_mb):
    size_threshold_bytes = size_threshold_mb * 1024 * 1024
    large_files = get_large_files(directory, size_threshold_bytes)

    if large_files:
        logger.warning(f"Files larger than {size_threshold_mb} MB:")
        for filepath, filesize in large_files:
            logger.warning(f"{filepath}: {format_size(filesize)}")
    else:
        logger.success(f"No files larger than {size_threshold_mb} MB found.")


@injected
async def build_image_with_rsync(
        a_system,
        logger,
        /,
        code,
        tag,
        push=False
):
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # let's replace RCOPY with COPY, and RSYNC with COPY

        logger.info(f"source dockerfile:\n{code}")

        new_docker_file = ""
        async with TaskGroup() as tg:
            for line in code.split("\n"):
                if line.startswith("RCOPY"):
                    cmd, src, dst = line.split()
                    dst = Path(dst)
                    new_docker_file += f"COPY {path_hash(dst)} {dst}\n"
                    tg.create_task(a_system(f"cp -r {src} {tmpdir / path_hash(dst)}"))
                elif line.startswith('RSYNC'):
                    items = line.split()
                    cmd, src, dst = items[:3]
                    options = items[3:]
                    src = Path(src)
                    dst = Path(dst)
                    rsync_dst = tmpdir / path_hash(dst)
                    assert not rsync_dst.exists(), "the destination of rsync already exists."
                    cmd = f"rsync -avH --progress --link-dest={src.expanduser()} {src.expanduser()}/ {rsync_dst}/"
                    if options:
                        cmd += " " + " ".join(options)
                        # cmd += f" --exclude={' --exclude='.join(excludes)}"
                    new_docker_file += f"COPY {path_hash(dst)} {dst}\n"
                    # escape command
                    cmd = " ".join([shlex.quote(arg) for arg in cmd.split()])
                    tg.create_task(a_system(cmd))
                    # await a_system(cmd)
                else:
                    new_docker_file += line + "\n"

        dockerfile_path = tmpdir / "Dockerfile"
        dockerfile_path.write_text(new_docker_file)

        logger.info(f"preprocessed dockerfile:\n {new_docker_file}")

        # I want to check the build context size
        log_large_files(tmpdir, 10)
        # can we do things like ncdu?

        await a_system(f"docker build -t {tag} {tmpdir}")
        await a_system(f"docker history {tag}")
        if push:
            await a_system(f"docker push {tag}")
        return tag



@injected
async def a_build_docker_no_buildkit(
        a_system,
        ml_nexus_debug_docker_build,
        /,
        tag,
        context_dir,
        options: str,
        push: bool = False,
        build_id=None
):
    await a_system(f"DOCKER_BUILDKIT=0 docker build {options} -t {tag} {context_dir}")
    if ml_nexus_debug_docker_build:
        await a_system(f"docker history {tag}")
    if push:
        await a_system(f"docker push {tag}")
    return tag





class BuildImageWithMacro:
    async def __call__(self, code, tag, push=False, use_cache=True, build_id=None):
        pass

@instance
async def docker_build_keyed_lock()->KeyedLock:
    return KeyedLock()

@injected
@asynccontextmanager
async def prepare_build_context_with_macro(
        a_system,
        logger,
        docker_build_keyed_lock: KeyedLock,
        /,
        code: list[Union[str, Block, RCopy, RsyncArgs]],

):
    """
    Introduce Priority Queue to process the codes.

    1. flatten the code as much as possible first.
    2. put macro into pqueue
    oops, for expanded ones , you need to prepend it.


    """
    assert isinstance(code, list), f"code must be a list of macro. but got {type(code)}"
    with TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # let's replace RCOPY with COPY, and RSYNC with COPY

        logger.info(f"source dockerfile:\n{pformat(code)}")

        cxt = BuildMacroContext(build_dir=tmpdir)

        macros_in_context = []
        try:
            async with TaskGroup() as tg:
                async def parse(macro: Macro):
                    match macro:
                        case str() as code:
                            return code
                        case Block(b):
                            return b
                        case RCopy(src, dst):
                            tg.create_task(a_system(f"cp -r {src} {tmpdir / path_hash(dst)}"))
                            return f"COPY {path_hash(dst)} {dst}"
                        case RsyncArgs(src, dst, excludes, options) as args:
                            rsync_dst = tmpdir / path_hash(dst.path)
                            assert not rsync_dst.exists(), "the destination of rsync already exists."
                            new_args: RsyncArgs = replace(args, dst=rsync_dst, hardlink=True)
                            new_args.__post_init__()  # validation
                            tg.create_task(new_args.run())
                            return f"COPY {path_hash(dst.path)} {dst.path}"
                        case tgt if is_async_context_manager(tgt):
                            assert tgt not in macros_in_context, f"recursive async context manager {tgt}"
                            logger.info(f"entering async context manager {tgt}")
                            macro = await tgt.__aenter__()
                            macros_in_context.append(tgt)
                            return await parse(macro)
                        case tgt if inspect.iscoroutine(tgt):
                            return await tgt
                        case func if callable(func):
                            return await parse(func(cxt))
                        case [*macros]:
                            code = ""
                            for m in macros:
                                while not isinstance(m, str):
                                    m = await parse(m)
                                code += m + "\n"
                            return code

                new_docker_file = await parse(code)

            docker_file_hash = md5(new_docker_file.encode()).hexdigest()
            dockerfile_path = tmpdir / "Dockerfile"
            dockerfile_path.write_text(new_docker_file)

            # raise NotImplementedError("I need to replace the RSYNC with COPY in the dockerfile")

            logger.info(f"preprocessed dockerfile:\n {new_docker_file}")

            # I want to check the build context size
            log_large_files(tmpdir, 1)
            # use du to check the context size:
            du_result = await a_system(f"du -s {tmpdir}")
            # open terminal at tmpdir, iterm
            size_bytes = int(du_result.stdout.strip().split()[0])
            size_mbytes = size_bytes / 1024 / 1024
            if size_mbytes > 50:
                logger.warning(
                    f"Build context size is {size_mbytes} MB, which is larger than 50 MB., use ncdu to check")
                await a_system(
                    f"""osascript -e 'tell application "iTerm" to create window with default profile' -e 'tell application "iTerm" to tell current session of current window to write text "cd {tmpdir}"'"""
                )
                await asyncio.sleep(100000)
            async with docker_build_keyed_lock.lock(dockerfile_path):
                yield cxt
        finally:
            async with TaskGroup() as tg:
                for macro in macros_in_context:
                    tg.create_task(macro.__aexit__(None, None, None))


@injected
async def build_image_with_macro(
        a_build_docker,
        prepare_build_context_with_macro,
        /,
        code: list[Union[str, Block, RCopy, RsyncArgs]],
        tag,
        push=False,
        use_cache=True,
        build_id: str = None
):

    assert isinstance(code, list), f"code must be a list of macro. but got {type(code)}"
    async with prepare_build_context_with_macro(
            code
    ) as cxt:
        cxt: BuildMacroContext
        cache_opt = "--no-cache" if not use_cache else ""
        await a_build_docker(tag=tag, context_dir=cxt.build_dir, options=cache_opt, push=push, build_id=build_id)
        return tag


simple_macro = [
    "FROM alpine",
    "RUN echo hello"
]

with design(
        docker_build_name="test_build"
):
    docker_image_tag = f"asia-northeast1-docker.pkg.dev/cyberagent-050/ailab-mf/test-project"
    test_build_with_macro: IProxy = build_image_with_macro(
        code=simple_macro,
        tag=docker_image_tag,
        push=False
    )
    test_push: IProxy = a_docker_push__local(docker_image_tag)

__meta_design__ = design(
    overrides=load_env_design,
)
