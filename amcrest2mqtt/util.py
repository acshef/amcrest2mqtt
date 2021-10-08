from datetime import timedelta
import typing as t
import platform
import subprocess

SYS_WINDOWS = platform.system().lower() == "windows"

def ping(host: str, timeout: t.Union[float, int, timedelta]=None) -> bool:
	if isinstance(timeout, timedelta):
		timeout = timeout.total_seconds()

	count_param = "-n" if SYS_WINDOWS else "-c"
	command = ["ping", count_param, "1"]
	if timeout:
		if SYS_WINDOWS:
			timeout *= 1000 # Convert to milliseconds
		command += ["-w" if SYS_WINDOWS else "-W", str(timeout)]
	command += [host]

	p = subprocess.run(
		command,
		stdout=subprocess.DEVNULL,
		stderr=subprocess.DEVNULL
	)

	return p.returncode == 0