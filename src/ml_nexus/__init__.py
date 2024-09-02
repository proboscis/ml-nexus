from pathlib import Path

from pinjected import *
from pinjected import instance

from ml_nexus.rsync_util import RsyncArgs


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

    default_design = design(
        env_result_download_path=Path("results").expanduser(),
        a_system=a_system_sequential,
        build_image_with_copy=build_image_with_copy,
        patch_rye_project=patch_rye_project,
        macro_preinstall_from_requirements_with_rye=macro_preinstall_from_requirements_with_rye__v2,
        patch_uv_dir=patch_uv_dir,
        gather_rsync_macros_project_def=gather_rsync_macros_project_def,
        macro_install_base64_runner=macro_install_base64_runner,
        a_build_docker=a_build_docker_no_buildkit,
        # Constructors
        new_DockerHostEnvironment=injected(DockerHostEnvironment),
        new_DockerBuilder=injected(DockerBuilder),
        new_RsyncArgs=injected(RsyncArgs),
        ml_nexus_debug_docker_build=True
    )
    return default_design


load_env_design = __load_default_design

__meta_design__ = design(
    overrides=load_env_design,
    # default_design_paths=[
    #     "ml_nexus.default_design"
    # ]
)
