"""Scripts must run unchanged without being echoed into application logs."""

import asyncio
import base64
import io
import logging
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pinjected import design

from ml_nexus.docker.builder.docker_builder import DockerBuilder
from ml_nexus.docker.builder.macros.base64_runner import (
    script_base64_runner as docker_runner,
)
from ml_nexus.script_runner import script_base64_runner as local_runner
from ml_nexus.script_runner import _update_runner_script
from ml_nexus.util import (
    CommandException,
    SystemCallEnd,
    SystemCallStart,
    SystemCallStdErr,
    SystemCallStdOut,
    _SystemCallEventReporter,
    a_system_parallel,
)

SECRET = "private-fixture-value-that-must-not-be-logged"


@pytest.mark.parametrize("build_fails", [False, True])
def test_builder_does_not_log_entrypoint_contents(build_fails: bool) -> None:
    output: io.StringIO = io.StringIO()
    logger: logging.Logger = logging.Logger("script-secrecy")
    logger.addHandler(logging.StreamHandler(output))
    script: str = f"export PRIVATE_VALUE='{SECRET}'\n"
    build: AsyncMock = AsyncMock(return_value="test-image")
    install: AsyncMock = AsyncMock(return_value="COPY entrypoint /entrypoint")
    if build_fails:
        build.side_effect = RuntimeError("build failed")
    builder: DockerBuilder = DockerBuilder(
        _logger=logger,
        _build_image_with_macro=build,
        _build_entrypoint_script=AsyncMock(return_value=script),
        _get_macro_entrypoint_installation=install,
        base_image="python:3.11-slim",
        name="secrecy-test",
        scripts=[script],
    )
    if build_fails:
        with pytest.raises(RuntimeError, match="build failed"):
            asyncio.run(builder.a_build("test-image"))
    else:
        assert asyncio.run(builder.a_build("test-image")) == "test-image"
    install.assert_awaited_once_with(script)
    assert builder.built.is_set() is not build_fails
    assert SECRET not in output.getvalue()
    assert script not in output.getvalue()


@pytest.mark.parametrize(
    "runner", [local_runner, docker_runner], ids=["local", "docker"]
)
@pytest.mark.parametrize("exit_code", [0, 7])
def test_runner_preserves_output_and_status_without_echoing_script(
    runner: object, exit_code: int
) -> None:
    runner_script: str = design().to_graph()[runner]
    script: str = (
        f"PRIVATE_VALUE='{SECRET}'\nprintf 'requested-output\\n'\nexit {exit_code}\n"
    )
    encoded: str = base64.b64encode(script.encode()).decode()
    result: subprocess.CompletedProcess[str] = subprocess.run(
        ["bash", "-s", "--", encoded],
        input=runner_script,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == exit_code
    assert "requested-output\n" in result.stdout
    assert SECRET not in result.stdout + result.stderr
    assert encoded not in result.stdout + result.stderr


def test_cached_runner_is_updated_after_upgrade(tmp_path: Path) -> None:
    runner_path: Path = tmp_path / "cache" / "base64_runner.sh"
    runner_path.parent.mkdir()
    runner_path.write_text('echo "$decoded_script"\n')
    runner_script: str = design().to_graph()[local_runner]
    _update_runner_script(runner_path, runner_script)
    assert runner_path.read_text() == runner_script
    first_update: int = runner_path.stat().st_mtime_ns
    _update_runner_script(runner_path, runner_script)
    assert runner_path.stat().st_mtime_ns == first_update


@pytest.mark.parametrize("exit_code", [0, 7])
def test_system_call_keeps_executable_data_out_of_events_and_errors(
    exit_code: int,
) -> None:
    events: list[object] = []

    async def collect(event: object) -> None:
        events.append(event)

    system = design(
        logger=logging.Logger("script-system"),
        ml_nexus_default_subprocess_limit=65536,
        ml_nexus_system_call_event_bus=collect,
        ml_nexus_system_call_semaphore=asyncio.Semaphore(1),
    ).to_graph()[a_system_parallel]
    script: str = f"PRIVATE_VALUE='{SECRET}'; printf 'executed\\n'; exit {exit_code}"
    encoded: str = base64.b64encode(script.encode()).decode()
    command: str = f"printf '%s' {encoded} | base64 -d | bash"
    if exit_code:
        with pytest.raises(CommandException) as failure:
            asyncio.run(system(command, display_command="execute private script"))
        assert failure.value.code == exit_code
        assert failure.value.stdout == "executed\n"
        assert SECRET not in str(failure.value)
        assert encoded not in str(failure.value)
    else:
        result = asyncio.run(system(command, display_command="execute private script"))
        assert result.stdout == "executed\n"
        assert result.exit_code == 0
    assert events
    assert all(event.command == "execute private script" for event in events)
    assert encoded not in repr(events)


@pytest.mark.parametrize("parallel_count", [1, 2, 3])
def test_event_reporting_finishes_all_commands(parallel_count: int) -> None:
    reporter: _SystemCallEventReporter = _SystemCallEventReporter()
    visualizer: MagicMock = MagicMock()
    visualizer.messages = {}

    def record_message(name: str, status: object, message: str) -> None:
        visualizer.messages[name] = message

    visualizer.add.side_effect = record_message
    reporter.get_visualizer = AsyncMock(return_value=visualizer)
    reporter.visualizer = visualizer

    async def exercise() -> None:
        for index in range(parallel_count):
            await reporter(SystemCallStart(id=str(index), command="safe description"))
        await reporter(
            SystemCallStdOut(id="0", command="safe description", text=b"ok\n")
        )
        await reporter(
            SystemCallStdErr(id="0", command="safe description", text=b"err\n")
        )
        for index in range(parallel_count):
            await reporter(
                SystemCallEnd(id=str(index), command="safe description", code=index % 2)
            )

    asyncio.run(exercise())
    assert reporter.states == {}
    if parallel_count > 1:
        visualizer.live.__exit__.assert_called_once_with(None, None, None)
        assert reporter.visualizer is None
    else:
        visualizer.live.__exit__.assert_not_called()
