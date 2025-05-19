import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Iterable, AsyncContextManager

from pinjected import *

from ml_nexus.docker.builder.macros.macro_defs import Block, RCopy, Macro
from ml_nexus.project_structure import ProjectDef, PlatformDependantPypi, ProjectDir
from ml_nexus.rsync_util import RsyncArgs
from ml_nexus.storage_resolver import IStorageResolver
from ml_nexus.testing.test_resources import default_ignore_set


@injected
async def docker__install_rye():
    return Block(f"""
RUN pip3 install --upgrade pip setuptools
ENV RYE_HOME="/opt/rye"
ENV PATH="$RYE_HOME/shims:$PATH"
RUN echo hello
RUN curl -sSf https://rye.astral.sh/get | RYE_NO_AUTO_INSTALL=1 RYE_INSTALL_OPTION="--yes" bash
RUN /opt/rye/shims/rye --version
RUN rye --version
RUN rye config --set-bool use-uv=true
RUN rye config --set-bool behavior.use-uv=true
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN ["bin/bash","-c","source /opt/rye/env"]
# RUN /root/.cargo/bin/uv --version # we the uv location might have changed
    """)


@injected
async def macros_install_python_with_rye(
        python_version_dir,
        pyproject_dir_in_container,
) -> Macro:
    return [
        RCopy(python_version_dir, pyproject_dir_in_container / ".python-version"),
        Block(f"""
# download python from .python-version
WORKDIR {pyproject_dir_in_container}
RUN rye fetch
""")
    ]


def create_latest_version_table(lines):
    table = defaultdict(list)
    unversioned = set()
    for line in lines:
        line = line.split("#")[0]
        if "==" in line:
            k, v = line.split("==")
            table[k].append(v)
        else:
            unversioned.add(line)
    unversioned = {k for k in unversioned if k not in table}
    return unversioned, {k: sorted(v)[-1] for k, v in table.items()}


@injected
async def extract_clean_requirements(
        storage_resolver,
        get_clean_requirements,
        /,
        pdef: ProjectDef) -> list[str]:
    additional_packages = []
    for ex in pdef.extra_dependencies:
        match ex:
            case PlatformDependantPypi('linux', pkg):
                additional_packages.append(pkg)
    pdir = pdef.dirs[0]
    assert pdir.kind == 'rye', f"The first project dir must be rye. got {pdir}"
    root = await storage_resolver.locate(pdir.id)
    lines = await get_clean_requirements(root, additional_packages)
    unversioned, version_table = create_latest_version_table(lines)
    lines = [f"{k}=={version_table[k]}" for k in version_table.keys()]
    return lines


@injected
async def remove_local_refs_from_lock(
        content: str
):
    lines = content.split("\n")
    lines = [line for line in lines if "@" not in line]
    lines = [line for line in lines if "file:///" not in line]
    lines = [line for line in lines if "-e file" not in line]
    lines = [line.split('#')[0] for line in lines]
    return "\n".join(lines)


@injected
@asynccontextmanager
async def create_clean_requirements_lock(
        storage_resolver,
        get_clean_requirements_str,
        /,
        base_image: str,  # for interface compatibility
        pdef: ProjectDef,
) -> AsyncContextManager[Path]:
    additional_packages = []
    for ex in pdef.extra_dependencies:
        match ex:
            case PlatformDependantPypi('linux', pkg):
                additional_packages.append(pkg)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        lines = ""
        pdir = pdef.dirs[0]
        assert pdir.kind == 'rye', f"The first project dir must be rye. got {pdir}"
        root = await storage_resolver.locate(pdir.id)
        lines += await get_clean_requirements_str(root, additional_packages)
        lines += "\n"
        lines = lines.split()
        unversioned, version_table = create_latest_version_table(lines)
        lines = [f"{k}=={version_table[k]}" for k in version_table.keys()]
        lines = "\n".join(lines)
        lines += "\n".join(unversioned)
        cleaned_lock = tmpdir / "cleaned_requirements.lock"
        cleaned_lock.write_text(lines)
        yield cleaned_lock


@injected
async def a_separate_requirements_to_stages(
        requirements: list[str],
        prefixes=('torch', 'tensorflow', 'google'),
) -> Iterable[Path]:
    lock = requirements

    stages = defaultdict(set)
    for d in lock:
        added = False
        for p in prefixes:
            if p in d:
                stages[p].add(d)
                added = True
        if not added:
            stages['other'].add(d)

    # the order is important. so,
    for stage in list(prefixes) + ['other']:
        deps = stages[stage]
        deps = sorted(deps)
        yield stage, deps


@injected
@asynccontextmanager
async def a_separate_locks_to_stages(
        a_separate_requirements_to_stages,
        /,
        lock_file: Path,
        prefixes=('torch', 'tensorflow', 'google'),
) -> AsyncContextManager[Iterable[Path]]:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock = lock_file.read_text().split("\n")
        locks = []

        async for stage, deps in a_separate_requirements_to_stages(lock, list(prefixes) + ['other']):
            lock = Path(tmpdir) / f"{stage}_requirements.lock"
            deps = sorted(deps)
            lock.write_text("\n".join(deps))
            locks.append(lock)

        yield locks


@injected
@asynccontextmanager
async def macro_install_uv_constraint(
        constraints: list[str]
):
    with tempfile.TemporaryDirectory() as tmpdir:
        filename = "uv_constraints.txt"
        constraint_path = Path(tmpdir) / filename
        constraint_path.write_text("\n".join(constraints))
        yield [
            RCopy(constraint_path, Path("/") / filename),
            f"ENV UV_CONSTRAINT={Path('/') / filename}"
        ]


@injected
@asynccontextmanager
async def macro_install_deps_via_staged_pyproject(
        a_separate_requirements_to_stages,
        extract_clean_requirements,
        storage_resolver: IStorageResolver,
        logger,
        macro_install_uv_constraint,
        /,
        tgt: ProjectDef
):
    deps: list[str] = await extract_clean_requirements(tgt)
    cum_deps = []
    # src_pyproject = tgt.default_working_dir / 'pyproject.toml'
    src_project_dir = await storage_resolver.locate(tgt.dirs[0].id)
    src_pyproject = src_project_dir / 'pyproject.toml'
    readme_path = src_project_dir / 'README.md'
    import toml
    pyproject_data = toml.loads(src_pyproject.read_text())
    assert readme_path.exists(), f"README.md must exist in the project root. {readme_path}"
    macros = [
        RCopy(readme_path, tgt.default_working_dir / 'README.md'),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        # Hack setuptools bug https://github.com/pypa/setuptools/issues/4519#issuecomment-2254983472
        constraint = "setuptools<72"
        macros += [
            macro_install_uv_constraint([constraint]),
        ]

        async for stage, deps in a_separate_requirements_to_stages(deps):
            cum_deps += deps
            pyproject_data['project']['dependencies'] = cum_deps
            staged_pyp_name = f"{stage}_pyproject.toml"
            new_pyproject = Path(tmpdir) / staged_pyp_name
            new_pyproject.write_text(toml.dumps(pyproject_data))
            macros += [
                RCopy(new_pyproject, tgt.default_working_dir / staged_pyp_name),
                f"RUN mv {staged_pyp_name} pyproject.toml",
                "RUN rye sync"
            ]
        logger.info(f"generated macros:{macros}")
        yield macros


@instance
def build_isolation():
    return False


@injected
async def macro_install_staged_rye_lock(
        gather_rsync_macros_project_def,
        storage_resolver,
        macro_install_uv_constraint,
        /,
        staged_locks: list[Path],
        project_pyproject_dir: Path,
        pdef: ProjectDef
):
    first_root = await storage_resolver.locate(pdef.dirs[0].id)

    install_locks_staged = []
    # the no-build-isolation is for avoiding recent setuptools bug.
    if build_isolation:
        macro_build_preparation = [
            f'RUN /root/.cargo/bin/uv pip install "setuptools<72" wheel poetry hatchling editables',
            macro_install_uv_constraint(["setuptools<72"]),
            "ENV UV_NO_BUILD_ISOLATION=true"  # this is to ensure
        ]
    else:
        macro_build_preparation = []
    # uv pip is not the same as pip and sometimes fail.
    # our option is to:
    """
    1. edit pyproject.toml by stage.
    # why didn't i do that? because that's complicated.
    """
    for staged_lock in staged_locks:
        opt = "--no-build-isolation" if build_isolation else ""
        install_locks_staged += [
            RCopy(staged_lock, project_pyproject_dir / staged_lock.name),
            f"RUN /root/.cargo/bin/uv pip install -r {staged_lock.name} {opt}"
        ]
    # We need to make a lock for torch related stuff separately.
    rsyncs = await gather_rsync_macros_project_def(pdef)

    code = [
        Block(f"""
        RUN mkdir -p {project_pyproject_dir}
        # here RCOPY is converted to COPY by the build_image_with_rsync. internally copies the files to tmpdir
        """),
        Block(f"""
        # build venv from the main pyproject.toml
        WORKDIR {project_pyproject_dir}
        # rye can't build venv from requirements.lock, so we do it directly using uv
        RUN /root/.cargo/bin/uv venv
        RUN /root/.cargo/bin/uv pip install poetry wheel
        """),
        macro_build_preparation,
        *install_locks_staged,
        *rsyncs,
        Block(f"""
        WORKDIR {project_pyproject_dir}
        # copy the dummy rye-venv.json to fool rye to use the venv in the job_working_dir
        """),
        get_dummy_rye_venv(project_pyproject_dir),
        "RUN rye sync"
    ]
    return code


def get_dummy_rye_venv(project_pyproject_dir):
    from returns.result import safe
    @safe
    def safe_read_text(path):
        return path.read_text().strip()
    @asynccontextmanager
    async def impl(cxt):
        rye_venv_path = project_pyproject_dir / ".venv/rye-venv.json"
        import json
        import re
        python= json.loads(rye_venv_path.read_text())['python']
        python_version = re.search(r'cpython@(.+)',python).group(1)
        dummy_rye_venv = dict(
            python=f"cpython@{python_version}",
            venv_path=f"{project_pyproject_dir}/.venv"
        )
        with tempfile.NamedTemporaryFile() as tmp:
            dummy_path = Path(tmp.name)
            dummy_path.write_text(json.dumps(dummy_rye_venv))
            yield RCopy(dummy_path, project_pyproject_dir / ".venv/rye-venv.json"),

    return impl


@injected
async def macro_preinstall_from_requirements_with_rye(
        create_clean_requirements_lock,
        a_separate_locks_to_stages,
        macro_install_staged_rye_lock,
        /,
        base_image: str,
        pdef: ProjectDef,
        project_pyproject_dir: Path,
) -> Macro:
    @asynccontextmanager
    async def impl(cxt):
        async with create_clean_requirements_lock(base_image, pdef) as cleaned_lock:
            async with a_separate_locks_to_stages(cleaned_lock) as staged_locks:
                yield await macro_install_staged_rye_lock(staged_locks, project_pyproject_dir, pdef)

    return impl


async def get_clean_pyproject(first_project, first_project_path):
    import toml
    orig_pyproject = (Path(first_project_path.expanduser()) / "pyproject.toml").read_text()
    orig_pyproject = toml.loads(orig_pyproject)
    deps = orig_pyproject['project']['dependencies']
    new_deps = []
    for dep in deps:
        if '@' not in dep:
            new_deps.append(dep)
    orig_pyproject['project']['dependencies'] = new_deps
    new_pyproject_path = Path("/tmp") / first_project.id / "cleaned_pyproject.toml"
    new_pyproject_path.write_text(toml.dumps(orig_pyproject))
    return new_pyproject_path


@injected
async def get_clean_requirements(
        a_system,
        /,
        project_root: Path,
        additional_packages: list[str]
) -> list[str]:
    with (tempfile.TemporaryDirectory() as tmpdir):
        # make symbolic link to .venv so that rye won't make new venv
        tmp = Path(tmpdir)
        (tmp / ".venv").symlink_to(project_root / ".venv")
        (tmp / ".python-version").symlink_to(project_root / ".python-version")
        pyproject_path = project_root / "pyproject.toml"
        tmp_pyproject = tmp / "pyproject.toml"
        tmp_pyproject.write_text(pyproject_path.read_text())
        if additional_packages:
            pkgs = ' '.join(additional_packages)
            await a_system(f"rye add --no-sync {pkgs}", working_dir=tmp)
        # it seems... locking outside the container returns different results.
        # so we need to...
        """
        0. copy dependent pyproject.py stuff to the container
        1. lock inside the container
        2. copy the lock cleaner to the container
        3. install staged locks
        4. copy the actual sources and rye sync.
        """
        await a_system(f"rye lock", working_dir=tmp)
        tmp_lock = tmp / "requirements.lock"
        lines = tmp_lock.read_text().split("\n")
    # now let's remove lines with @
    blacklist = {'pyobjc-framework-quartz'}

    lines = [line for line in lines if "@" not in line]
    lines = [line for line in lines if "file:///" not in line]
    lines = [line for line in lines if "-e file" not in line]
    lines = [line for line in lines if line.strip() not in blacklist]
    lines = [line for line in lines if not line.strip().startswith('pyobjc')]  # remove mac related stuff
    lines = [line.split('#')[0] for line in lines]
    lines = [l for l in lines if l.strip()]
    return lines


@injected
@asynccontextmanager
async def get_lock_via_container(
        storage_resolver: IStorageResolver,
        docker__install_rye,
        macros_install_python_with_rye,
        gather_rsync_macros_project_def,
        prepare_build_context_with_macro,
        a_build_docker_for_output,
        logger,
        /,
        base_image: str,
        pdef: ProjectDef
):
    """
    1. install rye
    2. rye lock
    :param storage_resolver:
    :param pdef:
    :return:
    """
    root_dir = pdef.dirs[0]
    root_path = await storage_resolver.locate(root_dir.id)
    pyproject_dir_in_container = Path("/sources") / root_dir.id

    """
    Reference: https://docs.docker.jp/engine/reference/commandline/build.html#:~:text=go/bin/vndr%20/-,Dockerfile,-%E3%82%92%20%2Do%20%E3%82%AA%E3%83%97%E3%82%B7%E3%83%A7%E3%83%B3
    """

    macros = [
        f"FROM {base_image} as rye_lock",
        "ARG DEBIAN_FRONTEND=noninteractive",
        "RUN apt-get update && apt-get install -y python3-pip python3-dev build-essential libssl-dev curl git clang",
        await docker__install_rye(),
        await macros_install_python_with_rye(root_path / ".python-version", pyproject_dir_in_container),
        await gather_rsync_macros_project_def(pdef),  # rsync sources :) so we can run rye lock!
        f"WORKDIR {pyproject_dir_in_container}",
        "RUN rye lock",
        "FROM scratch AS rye_lock_export",
        f"COPY --from=rye_lock {pyproject_dir_in_container / 'requirements.lock'} /",
    ]
    build_id = base_image.replace("/", "_").replace(":", "_")
    build_id += "_" + root_dir.id + "_lock"

    async with prepare_build_context_with_macro(macros) as cxt:
        # now i want to build and get output.
        with tempfile.TemporaryDirectory() as local_output_dir:
            await a_build_docker_for_output(cxt.build_dir, build_id=build_id, local_output_dir=local_output_dir)
            yield Path(local_output_dir) / 'requirements.lock'


@injected
async def macro_preinstall_from_requirements_with_rye__v2(
        a_separate_locks_to_stages,
        macro_install_staged_rye_lock,
        get_lock_via_container,
        remove_local_refs_from_lock,
        /,
        base_image: str,
        pdef: ProjectDef,
        project_pyproject_dir: Path,
) -> Macro:
    @asynccontextmanager
    async def impl(cxt):
        async with get_lock_via_container(base_image, pdef) as original_lock:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                cleaned_lock = tmpdir / "cleaned_requirements.lock"
                cleaned_lock.write_text(await remove_local_refs_from_lock(original_lock.read_text()))
                async with a_separate_locks_to_stages(cleaned_lock) as staged_locks:
                    yield await macro_install_staged_rye_lock(staged_locks, project_pyproject_dir, pdef)

    return impl


@injected
async def get_clean_requirements_str(
        get_clean_requirements,
        /,
        project_root: Path,
        additional_packages: list[str]
):
    lines = await get_clean_requirements(project_root, additional_packages)
    lines = "\n".join(lines)
    return lines


@injected
async def get_clean_requirements_lock(
        logger,
        get_clean_requirements_str,
        /,
        project_root: Path,
        additional_packages: list[str]
) -> Path:
    dst = project_root / "requirements.lock"
    lines = get_clean_requirements_str(project_root, additional_packages)
    dst.write_text(lines)
    logger.warning(f"cleaned requirements.lock:\n{lines}")
    return dst


@instance
async def _test_get_lock(
        logger,
        get_lock_via_container,
):
    async with get_lock_via_container(
            base_image="python:3.9",
            project=ProjectDef(
                dirs=[
                    ProjectDir(
                        id="ml-nexus",
                        kind='rye',
                        excludes=default_ignore_set
                    )
                ]
            )
    ) as lock:
        logger.info(f"lockfile:{lock}")
        logger.info(f"lockfile content:{lock.read_text()}")


with design(
        new_RsyncArgs=injected(RsyncArgs)
):
    run_test_get_lock: IProxy = _test_get_lock

__meta_design__ = design()
