import typing as t

from amcrest import AmcrestCamera, AmcrestError

from .config import Config
from .const import *
from .device import Device


__all__ = ["Camera", "AmcrestError"]


_T = t.TypeVar("_T")


class Camera:
	def __init__(self, *args, **kwargs):
		self._camera = AmcrestCamera(*args, **kwargs).camera

	def __getattr__(self, attr):
		return getattr(self._camera, attr)

	def get_config(self, name: str, type: t.Callable[[str], _T]=str) -> _T:
		ret = self._camera.command(f"configManager.cgi?action=getConfig&name={name}")
		line = ret.content.decode().strip() # Should be of the form "key.subkey.subsubkey=value"
		_, _, value = line.partition("=")
		return type(value.strip())

	def set_config(self, values: t.Dict[str,t.Any]):
		url = "configManager.cgi?action=setConfig"
		for key, value in values.items():
			url += f"&{key}={value}"
		ret = self._camera.command(url)
		return "ok" in ret.content.decode().lower()

	def get_device(self):
		device_type = self._camera.device_type.replace("type=", "").strip()
		serial_number = self._camera.serial_number.strip()
		sw_version = self._camera.software_information[0].replace("version=", "").strip()
		device_name = self._camera.machine_name.replace("name=", "").strip()

		return Device(
			name=device_name,
            model=device_type,
            serial_no=serial_number,
            sw_version=sw_version
		)

	@classmethod
	def from_config(cls, config: Config) -> "Camera":
		return cls(config.amcrest_host, config.amcrest_port, config.amcrest_username, config.amcrest_password)

	def events(self) -> t.Iterable[t.Tuple[str, dict]]:
		for code, payload in self._camera.event_actions(
			CAMERA_EVENTS_SPECIFIER,
			retries=CAMERA_EVENTS_RETRIES,
			timeout_cmd=CAMERA_EVENTS_TIMEOUT
		):
			yield code, payload