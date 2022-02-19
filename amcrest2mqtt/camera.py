import typing as t

from amcrest import AmcrestCamera, AmcrestError

from .const import *
from .device import Device


__all__ = ["Camera", "AmcrestError"]


_T = t.TypeVar("_T")


class Camera:
    """
    Wrapper for amcrest.AmcrestCamera().camera, which is an instance of amcrest.ApiWrapper()
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        device_name: t.Optional[str],
        *args,
        **kwargs,
    ):
        self._camera = AmcrestCamera(host, port, username, password, *args, **kwargs).camera
        self._device_name = device_name

    def __getattr__(self, attr):
        return getattr(self._camera, attr)

    def get_config(self, name: str, type: t.Callable[[str], _T] = str) -> _T:
        ret = self._camera.command(f"configManager.cgi?action=getConfig&name={name}")
        line = ret.content.decode().strip()  # Should be of the form "key.subkey.subsubkey=value"
        _, _, value = line.partition("=")
        return type(value.strip())

    def set_config(self, values: t.Dict[str, t.Any]):
        url = "configManager.cgi?action=setConfig"
        for key, value in values.items():
            if isinstance(value, bool):
                value = str(value).lower()  # "true" or "false"
            url += f"&{key}={value}"
        ret = self._camera.command(url)
        return "ok" in ret.content.decode().lower()

    def get_device(self):
        device_type = self._camera.device_type.replace("type=", "").strip()
        serial_number = self._camera.serial_number.strip()
        sw_version = self._camera.software_information[0].replace("version=", "").strip()
        device_name = self._device_name or self._camera.machine_name.replace("name=", "").strip()

        return Device(
            name=device_name,
            model=device_type,
            serial_no=serial_number,
            sw_version=sw_version,
        )

    def events(self) -> t.Iterable[t.Tuple[str, dict]]:
        for code, payload in self._camera.event_actions(
            CAMERA_EVENTS_SPECIFIER,
            retries=CAMERA_EVENTS_RETRIES,
            timeout_cmd=CAMERA_EVENTS_TIMEOUT,
        ):
            yield code, payload
