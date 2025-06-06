from pathlib import Path

from pinjected import *


@instance
async def __ml_nexus_test_design():
    from ml_nexus.docker_env import DockerHostMounter
    from ml_nexus.storage_resolver import local_storage_resolver

    from ml_nexus.docker.builder.docker_env_with_schematics import DockerHostPlacement

    return design(
        env_result_download_path=Path(".").expanduser(),
        storage_resolver=local_storage_resolver(
            source_root=Path("~/repos").expanduser().absolute(),
        ),
        default_docker_host_mounter=injected(DockerHostMounter)(
            host_resource_root=Path("/tmp/ml_nexus_resources")
        ),
        default_docker_host_placement=DockerHostPlacement(
            cache_root=Path("/internal_tank/cache"),
            resource_root=Path("/internal_tank/resources"),
            source_root=Path("/internal_tank/sources"),
            direct_root=Path("/internal_tank/direct_mount"),
        ),
    )


ml_nexus_test_design = __ml_nexus_test_design
