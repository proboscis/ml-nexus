from pinjected import *
from pinjected.ide_supports.intellij.config_creator_for_env import idea_config_creator_from_envs

from ml_nexus.docker.builder.builder_utils.base_builder import schematics_with_uv
from ml_nexus.docker_env import DockerHostEnvironment
from ml_nexus.docker.builder.docker_env_with_schematics import DockerEnvFromSchematics
from ml_nexus.docker.builder.builder_utils.docker_for_rye import docker_builder__for_rye_v2, schematics_with_rye
from ml_nexus.testing import ml_nexus_test_design
from ml_nexus.testing.test_resources import test_project

builder = docker_builder__for_rye_v2(
    target=test_project,
    base_image="ubuntu:20.04",
)

uv_schematics = schematics_with_uv(target=test_project)
rye_schematics = schematics_with_rye(target=test_project)

docker_env = injected(DockerEnvFromSchematics)(
    project=test_project,
    schematics=uv_schematics,
    docker_host=injected('ml_nexus_test_docker_host')
)
docker_env_rye = injected(DockerEnvFromSchematics)(
    project=test_project,
    schematics=rye_schematics,
    docker_host=injected("ml_nexus_test_docker_host")
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




@instance
def logger():
    from loguru import logger
    return logger


@instance
def get_hostname(logger, /, ):
    import socket
    hostname = socket.gethostname()
    logger.info(f"Running on {hostname}")


test_docker_env_from_schema: IProxy = docker_env.run_script("echo hello world")

__meta_design__ = design(
    overrides=ml_nexus_test_design,
    custom_idea_config_creator=idea_config_creator_from_envs([
        "ml_nexus.testing.multi_environments.docker_env",
        "ml_nexus.testing.multi_environments.docker_env_rye",
    ])
)
