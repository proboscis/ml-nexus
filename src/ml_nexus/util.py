import asyncio
import os
import uuid
from typing import Protocol

from pinjected.compatibility.task_group import TaskGroup
from dataclasses import dataclass, field

from loguru import logger
from pinjected import *

from ml_nexus.rsync_util import RsyncArgs


@dataclass
class PsResult:
    stdout: str
    stderr: str
    exit_code: int


def random_hex_color():
    import random

    # choose readable light colors in HSV space
    h = random.randint(0, 360)
    s = random.randint(50, 100)
    v = random.randint(80, 100)
    # now convert to hex
    import colorsys

    rgb = colorsys.hsv_to_rgb(h / 360, s / 100, v / 100)
    return f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"


async def yield_from_stream_safe(stream):
    while True:
        try:
            async for line in stream:
                yield line
        except ValueError as e:
            logger.error(f"error during decoding stream: {e}")
        else:
            break


def log_with_color_id(stream_id, text, color):
    from loguru import logger

    logger = logger.opt(colors=True)
    text = escape_loguru_tags(text)
    text = text[:-1]  # remove the newline
    try:
        colored = f"<normal><fg {color}>[{stream_id}]</fg {color}>{text}</normal>"
        logger.debug(colored)  # Print in real-time
    except ValueError:
        logger.debug(f"[{stream_id}]{text}")


async def stream_and_capture_output(
    stream, display=True, stream_id=None, color: str | None = None
):
    output = []
    buf = []
    if color is None:
        color = random_hex_color()
    if stream_id is None:
        stream_id = uuid.uuid4().hex[:6]
    else:
        stream_id = escape_loguru_tags(stream_id)

    async for line in yield_from_stream_safe(stream):
        decoded_line = line.decode()
        if display and decoded_line.endswith("\n"):
            text = "".join(buf) + decoded_line
            log_with_color_id(stream_id, text, color)
            buf = []
        output.append(decoded_line)
    return "".join(output)


def escape_loguru_tags(text):
    return text.replace("<", r"\<")


class CommandException(Exception):
    def __init__(self, message, code, stdout, stderr):
        super().__init__(message)
        self.message = message
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

    def __reduce__(self):
        return self.__class__, (self.message, self.code, self.stdout, self.stderr)


class SystemCall(Protocol):
    async def __call__(
        self,
        command: str,
        env: dict | None = None,
        working_dir=None,
        *,
        display_command: str | None = None,
    ) -> PsResult:
        """
        run a command in the system.
        :param command:
        :param env:
        :param working_dir:
        :return:
        """
        ...


class ISystemCallEvent(Protocol):
    id: str
    command: str


@dataclass
class SystemCallStart(ISystemCallEvent):
    id: str
    command: str


@dataclass
class SystemCallEnd(ISystemCallEvent):
    id: str
    command: str
    code: int


@dataclass
class SystemCallStdOut(ISystemCallEvent):
    id: str
    command: str
    text: bytes


@dataclass
class SystemCallStdErr(ISystemCallEvent):
    id: str
    command: str
    text: bytes


class MLNexusSystemCallEventBus(Protocol):
    async def __call__(self, event: ISystemCallEvent): ...


@dataclass
class SystemCallState:
    id: str
    name: str
    command: str
    status: str
    message: str


@dataclass
class _SystemCallEventReporter:
    states: dict[str, SystemCallState] = field(default_factory=dict)
    visualizer: object = None

    async def get_visualizer(self):
        if self.visualizer is None:
            from pinjected.test_helper.rich_task_viz import RichTaskVisualizer

            self.visualizer = RichTaskVisualizer()
            self.visualizer.live.__enter__()
        return self.visualizer

    async def single(self, event: ISystemCallEvent):
        match event:
            case SystemCallStart(command=command):
                logger.info(f"running command=>{command}")
            case SystemCallEnd(command=command, code=0):
                logger.success(f"command <<{command}>> finished with ExitCode:0")
            case SystemCallEnd(command=command, code=code):
                logger.error(f"command: <<{command}>> failed with code {code}.")
            case SystemCallStdOut(text=text):
                logger.info(text.decode()[:-1])
            case SystemCallStdErr(text=text):
                logger.error(text.decode()[:-1])
            case _:
                raise ValueError(f"unexpected event {event}")

    async def start_parallel(self):
        from rich.spinner import Spinner

        viz = await self.get_visualizer()
        for state in self.states.values():
            if state.name not in viz.messages:
                status = (
                    Spinner("aesthetic") if state.status == "started" else state.status
                )
                viz.add(name=state.name, status=status, message=state.message)

    async def end_parallel(self, event: SystemCallEnd):
        state = self.states[event.id]
        viz = await self.get_visualizer()
        viz.update_status(state.name, "Finished with code " + str(event.code))
        if event.code == 0:
            viz.remove(state.name)
        if len(self.states) == 2:
            self.visualizer.live.__exit__(None, None, None)
            self.visualizer = None

    async def parallel(self, event: ISystemCallEvent):
        match event:
            case SystemCallStart():
                await self.start_parallel()
            case SystemCallEnd():
                await self.end_parallel(event)
            case SystemCallStdOut() | SystemCallStdErr():
                viz = await self.get_visualizer()
                state = self.states[event.id]
                viz.update_message(state.name, state.message)

    async def publish(self, event: ISystemCallEvent):
        if len(self.states) > 1:
            await self.parallel(event)
        else:
            await self.single(event)

    async def start(self, event: SystemCallStart):
        name = f"{event.id[:6]}:{event.command[:200]}"
        self.states[event.id] = SystemCallState(
            id=event.id, name=name, command=event.command, status="started", message=""
        )
        await self.publish(event)

    async def end(self, event: SystemCallEnd):
        state = self.states[event.id]
        state.message = f"Finished with code {event.code}"
        state.status = "finished"
        await self.publish(event)
        if len(self.states) == 2:
            await self.single(event)
        del self.states[event.id]

    async def output(self, event: SystemCallStdOut | SystemCallStdErr):
        state = self.states[event.id]
        state.message = event.text.decode()[:-1]
        state.status = "running"
        await self.publish(event)

    async def __call__(self, event: ISystemCallEvent):
        match event:
            case SystemCallStart():
                await self.start(event)
            case SystemCallEnd():
                await self.end(event)
            case SystemCallStdOut() | SystemCallStdErr():
                await self.output(event)
            case _:
                raise ValueError(f"unexpected event {event}")


@instance
async def ml_nexus_system_call_event_bus() -> MLNexusSystemCallEventBus:
    """Report command events, switching to a live view for concurrent commands."""
    return _SystemCallEventReporter()


@instance
async def ml_nexus_system_call_semaphore():
    from asyncio import Semaphore

    return Semaphore(20)


@injected
async def a_system_parallel(
    logger,
    ml_nexus_default_subprocess_limit,
    ml_nexus_system_call_event_bus,
    ml_nexus_system_call_semaphore,
    /,
    command: str,
    env: dict | None = None,
    working_dir=None,
    *,
    display_command: str | None = None,
):
    # Keep executable data separate from the description exposed to observers.
    logged_command: str = command if display_command is None else display_command
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)

    # logger.info(f"running command=>{command}")
    # color = random_hex_color()
    async with ml_nexus_system_call_semaphore:
        stream_id = uuid.uuid4().hex[:12]
        await ml_nexus_system_call_event_bus(
            SystemCallStart(id=stream_id, command=logged_command)
        )

        # prev_state = await a_get_stty_state()

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            # stdin = asyncio.subprocess.PIPE,
            # WARNING! STDIN must be set, or the pseudo terminal will get reused and mess up the terminal
            env=new_env,
            cwd=working_dir,
            limit=ml_nexus_default_subprocess_limit,
        )

        # Stream and capture stdout and stderr

        async def task_decode_stream(stream) -> str:
            lines = ""
            async for line in yield_from_stream_safe(stream):
                await ml_nexus_system_call_event_bus(
                    SystemCallStdOut(id=stream_id, command=logged_command, text=line)
                )
                lines += line.decode()[:-1] + "\n"
            return lines

        # stdout_future = stream_and_capture_output(proc.stdout, stream_id=stream_id + "_stdout", color=color)
        # stderr_future = stream_and_capture_output(proc.stderr, stream_id=stream_id + "_stderr", color=color)
        stdout, stderr = await asyncio.gather(
            task_decode_stream(proc.stdout), task_decode_stream(proc.stderr)
        )

        result: int = await proc.wait()  # Wait for the subprocess to exit
        await ml_nexus_system_call_event_bus(
            SystemCallEnd(id=stream_id, command=logged_command, code=result)
        )
        # logger.info(f"command finished with:\n{stdout},{stderr}\nExitCode:{result}")
        if result == 0:
            # logger.success(f"command <<{command}>> finished with ExitCode:{result}")
            pass
        if result != 0:
            # logger.error(f"command: <<{command}>> failed with code {result}.")
            raise CommandException(
                f"command: <<{logged_command}>> failed with code {result}."
                f"\nstdout: {stdout}"
                f"\nstderr: {stderr}",
                code=result,
                stdout=stdout,
                stderr=stderr,
            )
    return PsResult(stdout, stderr, exit_code=result)


a_system = a_system_parallel


@instance
async def system_lock():
    return asyncio.Lock()


@injected
async def a_system_sequential(
    system_lock,
    a_system_parallel: SystemCall,
    /,
    command: str,
    env: dict | None = None,
    working_dir=None,
    *,
    display_command: str | None = None,
):
    async with system_lock:
        return await a_system_parallel(
            command, env, working_dir, display_command=display_command
        )


@instance
async def test_a_system_newlines(new_RsyncArgs, a_system):
    async with TaskGroup() as tg:
        rsync = new_RsyncArgs(".", "/tmp/test", hardlink=True)
        for i in range(10):
            tg.create_task(rsync.run())


@injected
async def a_system_secret(
    ml_nexus_system_call_semaphore,
    ml_nexus_default_subprocess_limit,
    /,
    command: str,
    env: dict | None = None,
    working_dir=None,
):
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)

    async with ml_nexus_system_call_semaphore:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            # WARNING! STDIN must be set, or the pseudo terminal will get reused and mess up the terminal
            env=new_env,
            cwd=working_dir,
            limit=ml_nexus_default_subprocess_limit,
        )

        # Stream and capture stdout and stderr

        async def task_decode_stream(stream) -> str:
            lines = ""
            async for line in yield_from_stream_safe(stream):
                lines += line.decode()[:-1] + "\n"
            return lines

        stdout, stderr = await asyncio.gather(
            task_decode_stream(proc.stdout), task_decode_stream(proc.stderr)
        )

        result: int = await proc.wait()  # Wait for the subprocess to exit
        if result == 0:
            pass
        if result != 0:
            raise CommandException(
                f"command: <<{command}>> failed with code {result}."
                f"\nstdout: {stdout}"
                f"\nstderr: {stderr}",
                code=result,
                stdout=stdout,
                stderr=stderr,
            )
    return PsResult(stdout, stderr, exit_code=result)


__meta_design__ = design(overrides=design(new_RsyncArgs=injected(RsyncArgs)))
