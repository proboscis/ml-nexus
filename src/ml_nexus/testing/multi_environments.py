from pathlib import Path

from pinjected import *
from pinjected.ide_supports.intellij.config_creator_for_env import (
    idea_config_creator_from_envs,
)

from ml_nexus.docker.builder.builder_utils.docker_for_rye import (
    docker_builder__for_rye_v2,
    schematics_with_rye,
)
from ml_nexus.docker.builder.builder_utils.schematics_for_setup_py import (
    schematics_with_setup_py,
    schematics_with_setup_py__install_on_container,
)
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.persistent import PersistentDockerEnvFromSchematics

from ml_nexus.project_structure import ProjectDef, ProjectDir
from ml_nexus.testing import ml_nexus_test_design
from ml_nexus.testing.test_resources import test_project

builder = docker_builder__for_rye_v2(
    target=test_project,
    base_image="ubuntu:20.04",
)

sam2_project = ProjectDef(dirs=[ProjectDir(id="segment-anything-2", kind="setup.py")])

# uv_schematics = schematics_with_uv(target=test_project)
rye_schematics = schematics_with_rye(target=test_project)
setup_py_schematics_of_sam2 = schematics_with_setup_py(
    target=sam2_project,
)
setup_py_pyvenv = schematics_with_setup_py__install_on_container(target=sam2_project)
# TODO auto select schematics depending on the target project structure.

docker_env = injected(DockerEnvFromSchematics)(
    project=test_project,
    schematics=rye_schematics,
    docker_host=injected("ml_nexus_test_docker_host"),
)
p_docker_env = injected(PersistentDockerEnvFromSchematics)(
    project=test_project,
    schematics=setup_py_schematics_of_sam2,
    docker_host=injected("ml_nexus_test_docker_host"),
    container_name="persistent-test",
)
docker_env_rye = injected(DockerEnvFromSchematics)(
    project=test_project,
    schematics=rye_schematics,
    docker_host=injected("ml_nexus_test_docker_host"),
)
docker_env_sam2 = injected(DockerEnvFromSchematics)(
    project=sam2_project,
    schematics=setup_py_schematics_of_sam2,
    docker_host=injected("ml_nexus_test_docker_host"),
)
docker_env_sam2_pyvenv = injected(DockerEnvFromSchematics)(
    project=sam2_project,
    schematics=setup_py_pyvenv,
    docker_host=injected("ml_nexus_test_docker_host"),
)

test_docker: IProxy = docker_env.run_script("""
echo ======== BEGIN SCRIPT ========
nvidia-smi
ls -lah
echo ======== END SCRIPT ========
""")

test_docker_rye: IProxy = docker_env_rye.run_script("""
echo ======== BEGIN SCRIPT ========
nvidia-smi
echo ======== END SCRIPT ========
""")

test_docker_sam2: IProxy = docker_env_sam2.run_script("""
echo ======== BEGIN SCRIPT ========
nvidia-smi
python --version
echo ======== END SCRIPT ========
""")

test_docker_persistent: IProxy = p_docker_env.run_script("""
echo ======== BEGIN SCRIPT ========
nvidia-smi
python --version
ls -lah
echo ======== END SCRIPT ========
""")
test_docker_pyvenv: IProxy = docker_env_sam2_pyvenv.run_script("""
echo ======== BEGIN SCRIPT ========
python --version
which python
echo ======== END SCRIPT ========
""")

stop_docker_peristent: IProxy = p_docker_env.stop()

test_upload: IProxy = Injected.procedure(
    p_docker_env.upload(
        local_path=Path("./src"), remote_path=Path("/dst")
    ).await__(),  # hmm, why is this not being awaited, be cause it has no 'awaitable' flag set...
    p_docker_env.run_script("ls -lah /dst"),
)

test_context: IProxy = (
    p_docker_env.run_context()
    .with_upload(Path("./src"))
    .run_script(f"""
echo ======== BEGIN SCRIPT ========
echo $UPLOAD_0
ls -lah $UPLOAD_0
echo $RUN_RESULT_DIR
ls -lah $RUN_RESULT_DIR
echo ======== END SCRIPT ========
""")
)


@instance
def logger():
    from loguru import logger

    return logger


@instance
def get_hostname(
    logger,
    /,
):
    import socket

    hostname = socket.gethostname()
    logger.info(f"Running on {hostname}")


test_docker_env_from_schema: IProxy = docker_env.run_script("echo hello world")

__meta_design__ = design(
    overrides=ml_nexus_test_design,
    custom_idea_config_creator=idea_config_creator_from_envs(
        [
            "ml_nexus.testing.multi_environments.docker_env",
            "ml_nexus.testing.multi_environments.docker_env_rye",
        ]
    ),
)
