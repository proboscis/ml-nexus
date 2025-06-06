from typing import Final

from ml_nexus.util import SystemCallStart, SystemCallStdOut, SystemCallStdErr, SystemCallEnd
from pinjected import injected
import re

_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(job-[^-]+-[^-]+).*?job:", flags=re.IGNORECASE
)


@injected
async def handle_ml_nexus_system_call_events__simple(logger, /, e):
    logger = logger.opt(raw=True)
    try:
        match e:
            case SystemCallStart(id=_id, command=cmd):
                logger.debug(f"system call {cmd} with id {_id}", tag=_id)
            case SystemCallStdOut(id=_id, command=cmd, text=stdout):
                text = stdout.decode()
                text = _PATTERN.sub(r"\1:", text)
                logger.info(f"[{_id}]\t" + text)
            case SystemCallStdErr(id=_id, command=cmd, text=stderr):
                text = stderr.decode()
                text = _PATTERN.sub(r"\1:", text)
                logger.info(f"[{_id}]\t" + text)
            case SystemCallEnd(id=_id, command=cmd, code=code):
                if code == 0:
                    logger.success(f"command {cmd} finished with code {code}", tag=_id)
                else:
                    logger.error(f"command {cmd} failed with code {code}", tag=_id)
            case _:
                logger.warning(f"unknown event {e}")
    except Exception as ex:
        logger.error(f"Error handling system call event: {e} \n {ex}")

        raise ex

