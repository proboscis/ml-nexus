from pathlib import Path
from typing import Any

from pinjected import *
from pinjected import instance


@instance
def ml_nexus_logger():
    from loguru import logger
    return logger


@instance
def ml_nexus_source_root__from_env(ml_nexus_logger):
    logger = ml_nexus_logger
    import os
    if "ML_NEXUS_SOURCE_ROOT" in os.environ:
        source_root = Path(os.environ["ML_NEXUS_SOURCE_ROOT"])
        logger.info(f"Source root set from env(ML_NEXUS_SOURCE_ROOT): {source_root}")
    else:
        logger.info(f"Source root not set in env:ML_NEXUS_SOURCE_ROOT")
        source_root = Path("~/sources").expanduser()
        logger.info(f"using default source root: {source_root}")
        logger.info(f"Note: you can override 'ml_nexus_source_root' in __meta_design__")
    return source_root


@instance
def ml_nexus_resource_root__from_env(ml_nexus_logger):
    logger = ml_nexus_logger
    import os
    if "ML_NEXUS_RESOURCE_ROOT" in os.environ:
        resource_root = Path(os.environ["ML_NEXUS_RESOURCE_ROOT"])
        logger.info(f"Resource root set from env(ML_NEXUS_RESOURCE_ROOT): {resource_root}")
    else:
        logger.info(f"Resource root not set in env:ML_NEXUS_RESOURCE_ROOT")
        resource_root = Path("~/resources").expanduser()
        logger.info(f"using default resource root: {resource_root}")
        logger.info(f"Note: you can override 'ml_nexus_resource_root' in __meta_design__")
    return resource_root


@instance
def local_storage_resolver_from_env(
        ml_nexus_logger,
        ml_nexus_source_root: Path,
        ml_nexus_resource_root: Path
):
    logger = ml_nexus_logger
    logger.info(
        f"Creating local storage resolver with source_root: {ml_nexus_source_root}, resource_root: {ml_nexus_resource_root}")
    logger.info(f"You can override storage resolver by setting 'storage_resolver' in __meta_design__")
    from ml_nexus.storage_resolver import DirectoryStorageResolver
    return DirectoryStorageResolver(ml_nexus_source_root) + DirectoryStorageResolver(ml_nexus_resource_root)


@instance
def default_docker_host_mounter__from_env(ml_nexus_resource_root: Path, new_DockerHostMounter):
    from ml_nexus.docker_env import DockerHostMounter
    return new_DockerHostMounter(
        host_resource_root=ml_nexus_resource_root
    )


@instance
def ml_nexus_default_docker_image_repo__from_env(ml_nexus_logger):
    import os
    if "ML_NEXUS_DEFAULT_DOCKER_IMAGE_REPO" in os.environ:
        ml_nexus_logger.info(f"Using docker image repo from env: {os.environ['ML_NEXUS_DEFAULT_DOCKER_IMAGE_REPO']}")
        return os.environ["ML_NEXUS_DEFAULT_DOCKER_IMAGE_REPO"]
    else:
        raise Exception(
            "ML_NEXUS_DEFAULT_DOCKER_IMAGE_REPO not found in env. please set 'ml_nexus_default_docker_image_repo' in __meta_design__ or set the env var")


@injected
def ml_nexus_get_env(ml_nexus_logger, /, key: str, default: Any = None) -> str:
    import os
    if key in os.environ:
        ml_nexus_logger.info(f"Using env var {key} from env: {os.environ[key]}")
        return os.environ[key]
    else:
        ml_nexus_logger.info(f"Env var {key} not found in env. using default:{default}")
        return default


@injected
def ml_nexus_get_env_path(ml_nexus_logger, /, key: str, default: Path | str) -> Path:
    import os
    if key in os.environ:
        ml_nexus_logger.info(f"Using env var {key} from env: {os.environ[key]}")
        return Path(os.environ[key])
    else:
        if default is None:
            raise Exception(f"Env var {key} not found in env. Please set {key} in env")
        else:
            ml_nexus_logger.info(f"Env var {key} not found in env. using default:{default}")
            return Path(default)


@instance
def ml_nexus_default_docker_host_placement__from_env(ml_nexus_default_docker_host_upload_root: Path):
    from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement

    return DockerHostPlacement(
        cache_root=ml_nexus_default_docker_host_upload_root / "cache",
        resource_root=ml_nexus_default_docker_host_upload_root / "resources",
        source_root=ml_nexus_default_docker_host_upload_root / "sources",
        direct_root=ml_nexus_default_docker_host_upload_root
    )


@instance
def __load_default_design():
    from ml_nexus.util import a_system_parallel, a_system_sequential

    from ml_nexus.docker.builder.docker_builder import DockerBuilder
    from ml_nexus.project_structure import ProjectDef
    from ml_nexus.project_structure import ProjectDir

    from ml_nexus.docker_env import DockerHostEnvironment
    from ml_nexus.docker.builder.builder_utils.building import build_image_with_copy
    from ml_nexus.docker.builder.builder_utils.patch_rye import patch_rye_project
    from ml_nexus.docker.builder.builder_utils.patch_uv import patch_uv_dir
    from ml_nexus.docker.builder.builder_utils.rye_util import macro_preinstall_from_requirements_with_rye__v2
    from ml_nexus.util import a_system_sequential
    from ml_nexus.docker.builder.builder_utils.common import gather_rsync_macros_project_def
    from ml_nexus.docker.builder.macros.base64_runner import macro_install_base64_runner
    from ml_nexus.docker.builder.builder_utils.building import a_build_docker_no_buildkit

    from ml_nexus.storage_resolver import local_storage_resolver
    from ml_nexus.rsync_util import RsyncArgs
    from ml_nexus.docker_env import DockerHostMounter
    from ml_nexus.docker.builder.builder_utils.docker_for_rye import build_entrypoint_script, \
        get_macro_entrypoint_installation
    default_design = design(
        env_result_download_path=Path("results").expanduser(),
        # a_system=a_system_sequential,
        a_system=a_system_parallel,
        build_image_with_copy=build_image_with_copy,
        patch_rye_project=patch_rye_project,
        macro_preinstall_from_requirements_with_rye=macro_preinstall_from_requirements_with_rye__v2,
        patch_uv_dir=patch_uv_dir,
        gather_rsync_macros_project_def=gather_rsync_macros_project_def,
        macro_install_base64_runner=macro_install_base64_runner,
        a_build_docker=a_build_docker_no_buildkit,
        # Constructors
        new_DockerHostEnvironment=injected(DockerHostEnvironment),
        new_DockerHostMounter=injected(DockerHostMounter),
        new_DockerBuilder=injected(DockerBuilder),
        new_RsyncArgs=injected(RsyncArgs),

        ml_nexus_debug_docker_build=True,
        ml_nexus_default_docker_host_upload_root=ml_nexus_get_env_path("ML_NEXUS_DEFAULT_DOCKER_HOST_UPLOAD_ROOT",
                                                                       "/tmp/ml_nexus"),
        ml_nexus_default_docker_image_repo=ml_nexus_default_docker_image_repo__from_env,
        # docker host mounter
        ml_nexus_default_docker_host_mounter=default_docker_host_mounter__from_env,
        ml_nexus_default_docker_host_placement=ml_nexus_default_docker_host_placement__from_env,
        # ENV Vars
        ml_nexus_source_root=ml_nexus_source_root__from_env,
        ml_nexus_resource_root=ml_nexus_resource_root__from_env,
        # Storage Resolver
        storage_resolver=local_storage_resolver_from_env,

        build_entrypoint_script=build_entrypoint_script,
        get_macro_entrypoint_installation=get_macro_entrypoint_installation,
    )

    return default_design


load_env_design = __load_default_design
from pinjected.test import test_tree

run_tests: IProxy = test_tree()

__meta_design__ = design(
    overrides=load_env_design,
    # default_design_paths=[
    #     "ml_nexus.default_design"
    # ]
)
