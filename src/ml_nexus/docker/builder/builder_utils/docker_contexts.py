from pinjected import *


@injected
async def a_docker_push__local(a_system, /, tag):
    """
    NOTE: A command like below maybe required.
    gcloud auth configure-docker asia-northeast1-docker.pkg.dev
    """
    await a_system(f"docker push {tag}")


__meta_design__ = design()
