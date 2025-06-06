from pinjected import instance, injected, design
from returns.future import future


@instance
@future
async def f_install_gcloud_command(a_system):
    """
    install gcloud command
    """
    try:
        a_system('gcloud --version')
    except Exception:
        await a_system("curl -sSL https://sdk.cloud.google.com | bash")


@injected
async def a_tag_to_repo(tag: str):
    return tag.split("/")[0]

@injected
async def a_setup_docker_credentials(tag):
    """
    Dummy function for setting up Docker credentials.
    This is a no-op and does not perform any actions.
    """
    pass

@injected
async def a_setup_docker_credentials__gcp(
        service_account_json_for_docker_push: str,
        a_system,
        f_install_gcloud_command,
        a_tag_to_repo,
        /,
        tag
):
    """
    Set up gcloud authentication for Google Container Registry using service account key.
    Activates the service account and configures Docker to use this auth for asia-northeast1-docker.pkg.dev.
    repo: asia-northeast1-docker.pkg.dev
    """
    import tempfile

    await f_install_gcloud_command

    # Create a temporary file for the service account key that will be auto-deleted
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(service_account_json_for_docker_push.encode('utf-8'))
        temp_file.flush()

        # Activate service account with the key file
        await a_system(f"gcloud auth activate-service-account --key-file={temp_file.name}")

        # Configure Docker to use gcloud credentials for Google Container Registry
        repo = await a_tag_to_repo(tag)
        await a_system(f"gcloud auth configure-docker {repo} --quiet")


@injected
async def a_docker_push__local(a_system, a_setup_docker_credentials, ml_nexus_docker_build_context, logger, /, tag):
    """
    Push docker image to registry with optional docker context
    """
    await a_setup_docker_credentials(tag)
    
    docker_cmd = "docker"
    if ml_nexus_docker_build_context:
        logger.info(f"Using Docker context for push: {ml_nexus_docker_build_context}")
        docker_cmd = f"docker --context {ml_nexus_docker_build_context}"
    
    await a_system(f"{docker_cmd} push {tag}")


__meta_design__ = design()
