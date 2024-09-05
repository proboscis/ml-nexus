import asyncio
import os
import uuid
from asyncio import TaskGroup
from dataclasses import dataclass

from loguru import logger
from pinjected import *

from ml_nexus.rsync_util import RsyncArgs


@dataclass
class PsResult:
    stdout: str
    stderr: str


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


async def stream_and_capture_output(stream, display=True, stream_id=None, color: str = None):
    output = []
    buf = []
    from loguru import logger
    logger = logger.opt(colors=True)
    if color is None:
        color = random_hex_color()
    if stream_id is None:
        stream_id = uuid.uuid4().hex[:6]
    else:
        stream_id = escape_loguru_tags(stream_id)
    async for line in stream:
        decoded_line = line.decode()
        if display:
            # logger.opt(record=True).info(decoded_line)  # Print in real-time
            if decoded_line.endswith('\n'):
                text = ''.join(buf) + decoded_line
                text = escape_loguru_tags(text)
                text = text[:-1]  # remove the newline
                colored = f"<normal><fg {color}>[{stream_id}]</fg {color}>{text}</normal>"
                logger.debug(colored)  # Print in real-time
                buf = []
            pass
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


@injected
async def a_system_parallel(
        logger,
        /,
        command: str, env: dict = None, working_dir=None):
    new_env = os.environ.copy()
    if env is not None:
        new_env.update(env)

    logger.info(f"running command=>{command}")

    # prev_state = await a_get_stty_state()

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE,
        # stdin = asyncio.subprocess.PIPE,
        # WARNING! STDIN must be set, or the pseudo terminal will get reused and mess up the terminal
        env=new_env,
        cwd=working_dir
    )

    # Stream and capture stdout and stderr
    color = random_hex_color()
    stream_id = command[:20] + uuid.uuid4().hex[:6]
    stdout_future = stream_and_capture_output(proc.stdout, stream_id=stream_id + "_stdout", color=color)
    stderr_future = stream_and_capture_output(proc.stderr, stream_id=stream_id + "_stderr", color=color)
    stdout, stderr = await asyncio.gather(stdout_future, stderr_future)

    result = await proc.wait()  # Wait for the subprocess to exit
    # logger.info(f"command finished with:\n{stdout},{stderr}\nExitCode:{result}")
    if result == 0:
        logger.success(f"command <<{command}>> finished with ExitCode:{result}")
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
    # curr_state = await a_get_stty_state()
    # if prev_state != curr_state:
    #     logger.warning(f"stty state changed by {command}!\n PREV:{prev_state} \n CURR:{curr_state}")
    # logger.info(f"stty state is {curr_state}")

    return PsResult(stdout, stderr)


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
