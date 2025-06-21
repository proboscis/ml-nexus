"""Centralized Docker command construction with context support"""

from typing import Optional

from pinjected import injected
from loguru import logger


@injected
async def a_docker_cmd(
    ml_nexus_docker_build_context: Optional[str] = None, /, base_cmd: str = "docker"
) -> str:
    """
    Build docker command with context if specified.

    Args:
        base_cmd: Base docker command (default: "docker")

    Returns:
        Docker command string with context if configured
    """
    if ml_nexus_docker_build_context:
        logger.info(f"Using Docker context: {ml_nexus_docker_build_context}")
        return f"{base_cmd} --context {ml_nexus_docker_build_context}"
    return base_cmd


@injected
async def a_get_docker_cmd(
    ml_nexus_docker_build_context: Optional[str] = None, /
) -> str:
    """
    Get docker command with context if specified.
    This is a simpler version that just returns the command string.

    Returns:
        Docker command string with context if configured
    """
    if ml_nexus_docker_build_context:
        return f"docker --context {ml_nexus_docker_build_context}"
    return "docker"
