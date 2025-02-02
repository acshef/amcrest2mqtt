from datetime import timedelta
import typing as t
import platform
import subprocess

from slugify import slugify as _slugify


SYS_WINDOWS = platform.system().lower() == "windows"

_T = t.TypeVar("_T", int, float)


def ping(host: str, timeout: t.Union[float, int, timedelta] = None) -> bool:
    if isinstance(timeout, timedelta):
        timeout = timeout.total_seconds()

    count_param = "-n" if SYS_WINDOWS else "-c"
    command = ["ping", count_param, "1"]
    if timeout:
        if SYS_WINDOWS:
            timeout *= 1000  # Convert to milliseconds
        command += ["-w" if SYS_WINDOWS else "-W", str(timeout)]
    command += [host]

    p = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    return p.returncode == 0


def slugify(text: str) -> str:
    return _slugify(text, separator="_")


def clamp(
    value: _T,
    *,
    min: t.Optional[t.Union[int, float]] = None,
    max: t.Optional[t.Union[int, float]] = None,
) -> _T:
    if min is not None and value < min:
        value = min
    if max is not None and value > max:
        value = max
    return value


def str2bool(value: t.Any) -> bool:
    if value is None:
        return False
    return str(value).lower().strip() not in ("no", "off", "false", "0", "")
