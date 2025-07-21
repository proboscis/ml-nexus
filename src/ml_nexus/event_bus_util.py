from typing import Final, Protocol, Any

from pinjected.picklable_logger import PicklableLogger

from ml_nexus.util import (
    SystemCallStart,
    SystemCallStdOut,
    SystemCallStdErr,
    SystemCallEnd,
)
from pinjected import injected
import re

_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(job-[^-]+-[^-]+).*?job:", flags=re.IGNORECASE
)


class AHandleMlNexusSystemCallEventsSimpleProtocol(Protocol):
    async def __call__(self, e: Any) -> None: ...


def _handle_start(logger: PicklableLogger, _id: str, cmd: str) -> None:
    logger.debug(f"SystemCall[{_id}]: <{cmd}>", tag=_id)


def _handle_stdout(logger: PicklableLogger, _id: str, stdout: bytes) -> None:
    text = stdout.decode()
    text = _PATTERN.sub(r"\1:", text)
    logger.info(f"[{_id}]\t" + text)


def _handle_stderr(logger: PicklableLogger, _id: str, stderr: bytes) -> None:
    text = stderr.decode()
    text = _PATTERN.sub(r"\1:", text)
    logger.info(f"[{_id}]\t" + text)


def _handle_end(logger: PicklableLogger, _id: str, cmd: str, code: int) -> None:
    if code == 0:
        logger.success(f"command {cmd} finished with code {code}", tag=_id)
    else:
        logger.error(f"command {cmd} failed with code {code}", tag=_id)


@injected(protocol=AHandleMlNexusSystemCallEventsSimpleProtocol)
async def a_handle_ml_nexus_system_call_events__simple(
    logger: PicklableLogger, /, e
) -> None:
    logger = logger.opt(raw=True)
    try:
        match e:
            case SystemCallStart(id=_id, command=cmd):
                _handle_start(logger, _id, cmd)
            case SystemCallStdOut(id=_id, text=stdout):
                _handle_stdout(logger, _id, stdout)
            case SystemCallStdErr(id=_id, text=stderr):
                _handle_stderr(logger, _id, stderr)
            case SystemCallEnd(id=_id, command=cmd, code=code):
                _handle_end(logger, _id, cmd, code)
            case _:
                logger.warning(f"unknown event {e}")
    except Exception as ex:
        logger.error(f"Error handling system call event: {e} \n {ex}")
        raise ex
