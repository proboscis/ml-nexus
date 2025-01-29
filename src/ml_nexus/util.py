import asyncio
import os
import uuid
from typing import Protocol

from pinjected.compatibility.task_group import TaskGroup
from dataclasses import dataclass

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
    async def decode_stream():
        async for line in stream:
            yield line

    while True:
        try:
            async for line in decode_stream():
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


async def stream_and_capture_output(stream, display=True, stream_id=None, color: str = None):
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
        if display:
            # logger.opt(record=True).info(decoded_line)  # Print in real-time
            if decoded_line.endswith('\n'):
                text = ''.join(buf) + decoded_line
                log_with_color_id(stream_id, text, color)
                buf = []
        output.append(decoded_line)
    return ''.join(output)


def escape_loguru_tags(text):
    return text.replace('<', '\<')


class CommandException(Exception):
    def __init__(self, message, code, stdout, stderr):
        super().__init__(message)
        self.message = message
        self.stdout = stdout
        self.stderr = stderr
        self.code = code

    def __reduce__(self):
        return self.__class__, (self.message, self.code, self.stdout, self.stderr)


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
    async def __call__(self, event: ISystemCallEvent):
        ...


@dataclass
class SystemCallState:
    id: str
    name: str
    command: str
    status: str
    message: str


@instance
async def ml_nexus_system_call_event_bus() -> MLNexusSystemCallEventBus:
    """
    a default implementation of the system call event bus. visualization focused.
    """

    from pinjected.test_helper.rich_task_viz import RichTaskVisualizer
    _viz: RichTaskVisualizer = None
    states: dict[str, SystemCallState] = dict()
    from rich.spinner import Spinner

    async def a_get_viz() -> RichTaskVisualizer:
        nonlocal _viz
        if _viz is None:
            _viz = RichTaskVisualizer()
            _viz.live.__enter__()
        return _viz

    # i dont want to use the visualizer until the task gets more than one.
    # how can i do that?
    # detect events for entering simultaneous and not
    async def impl_single(event: ISystemCallEvent):
        match event:
            case SystemCallStart(id=id, command=command):
                logger.info(f"running command=>{command}")
            case SystemCallEnd(id=id, command=command, code=0):
                logger.success(f"command <<{command}>> finished with ExitCode:0")
            case SystemCallEnd(id=id, command=command, code=_code):
                logger.error(f"command: <<{command}>> failed with code {_code}.")
            case SystemCallStdOut(id=id, command=command, text=text):
                logger.info(text.decode()[:-1])
            case SystemCallStdErr(id=id, command=command, text=text):
                logger.error(text.decode()[:-1])
            case _:
                raise ValueError(f"unexpected event {event}")

    async def impl_parallel(event: ISystemCallEvent):
        nonlocal _viz
        match event:
            case SystemCallStart(id=id, command=command):
                state = states[id]
                viz = await a_get_viz()
                # we have to start from second task.
                for task, _state in states.items():
                    if _state.name not in viz.messages:
                        if _state.status == 'started':
                            status = Spinner('aesthetic')
                        else:
                            status = _state.status
                        viz.add(name=_state.name, status=status, message=_state.message)

            case SystemCallEnd(id=id, command=command, code=code):
                state = states[id]
                viz = await a_get_viz()
                viz.update_status(state.name, 'Finished with code ' + str(code))
                if code == 0:
                    viz.remove(state.name)
                if len(states) == 2:
                    _viz.live.__exit__(None, None, None)
                    _viz = None
            case SystemCallStdOut(id=id, command=command, text=text):
                viz = await a_get_viz()
                state = states[id]
                viz.update_message(state.name, state.message)
            case SystemCallStdErr(id=id, command=command, text=text):
                viz = await a_get_viz()
                state = states[id]
                viz.update_message(state.name, state.message)

    async def impl(event: ISystemCallEvent):
        match event:
            case SystemCallStart(id=id, command=command):
                name = f"{id[:6]}:{command[:200]}"
                states[id] = SystemCallState(id=id, name=name, command=command, status='started', message='')
                if len(states) > 1:
                    await impl_parallel(event)
                else:
                    await impl_single(event)
            case SystemCallEnd(id=id, command=command, code=code):
                state = states[id]
                state.message = f"Finished with code {code}"
                state.status = 'finished'
                if len(states) == 2:
                    await impl_parallel(event)  #
                    await impl_single(event)
                elif len(states) > 2:
                    await impl_parallel(event)
                else:
                    await impl_single(event)
                del states[id]
                # logger.warning(f"states:{states}")
            case SystemCallStdOut(id=id, command=command, text=text):
                state = states[id]
                state.message = text.decode()[:-1]
                state.status = 'running'
                if len(states) > 1:
                    await impl_parallel(event)
                else:
                    await impl_single(event)
            case SystemCallStdErr(id=id, command=command, text=text):
                state = states[id]
                state.message = text.decode()[:-1]
                state.status = 'running'
                if len(states) > 1:
                    await impl_parallel(event)
                else:
                    await impl_single(event)
            case _:
                raise ValueError(f"unexpected event {event}")

    return impl


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
        command: str, env: dict = None, working_dir=None):
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)

    # logger.info(f"running command=>{command}")
    # color = random_hex_color()
    async with ml_nexus_system_call_semaphore:
        stream_id = uuid.uuid4().hex[:12]
        await ml_nexus_system_call_event_bus(SystemCallStart(id=stream_id, command=command))

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
                await ml_nexus_system_call_event_bus(SystemCallStdOut(id=stream_id, command=command, text=line))
                lines += line.decode()[:-1] + "\n"
            return lines

        # stdout_future = stream_and_capture_output(proc.stdout, stream_id=stream_id + "_stdout", color=color)
        # stderr_future = stream_and_capture_output(proc.stderr, stream_id=stream_id + "_stderr", color=color)
        stdout, stderr = await asyncio.gather(
            task_decode_stream(proc.stdout),
            task_decode_stream(proc.stderr)
        )

        result: int = await proc.wait()  # Wait for the subprocess to exit
        await ml_nexus_system_call_event_bus(SystemCallEnd(id=stream_id, command=command, code=result))
        # logger.info(f"command finished with:\n{stdout},{stderr}\nExitCode:{result}")
        if result == 0:
            # logger.success(f"command <<{command}>> finished with ExitCode:{result}")
            pass
        if result != 0:
            logger.error(f"command: <<{command}>> failed with code {result}.")
            raise CommandException(
                f"command: <<{command}>> failed with code {result}."
                f"\nstdout: {stdout}"
                f"\nstderr: {stderr}",
                code=result,
                stdout=stdout,
                stderr=stderr
            )
    return PsResult(stdout, stderr, exit_code=result)


a_system = a_system_parallel


@instance
async def system_lock():
    return asyncio.Lock()


@injected
async def a_system_sequential(system_lock, a_system_parallel, /, command: str, env: dict = None, working_dir=None):
    async with system_lock:
        return await a_system_parallel(command, env, working_dir)


@instance
async def test_a_system_newlines(
        new_RsyncArgs,
        a_system):
    async with TaskGroup() as tg:
        rsync = new_RsyncArgs(".", "/tmp/test", hardlink=True)
        for i in range(10):
            tg.create_task(rsync.run())


__meta_design__ = design(
    overrides=design(
        new_RsyncArgs=injected(RsyncArgs)
    )
)
