from typing import NamedTuple

from amcrest import AmcrestCamera

from .const import *
from .util import slugify


class Device(NamedTuple):
	name: str
	model: str
	serial_no: str
	sw_version: str
	manufacturer = MANUFACTURER
	via_device = APP_NAME

	@property
	def slug(self) -> str:
		return slugify(self.name)

	def as_mqtt_device_dict(self) -> dict:
		return {
			"name": self.name,
			"manufacturer": self.manufacturer,
			"model": self.model,
			"identifiers": self.serial_no,
			"sw_version": self.sw_version,
			"via_device": self.via_device
		}

	@property
	def topic(self) -> str:
		return f"{APP_NAME}/{self.serial_no}"

	@property
	def status_topic(self) -> str:
		return f"{self.topic}/status"

	@property
	def event_topic(self) -> str:
		return f"{self.topic}/event"

	@classmethod
	def from_amcrest_camera(cls, camera: AmcrestCamera) -> "Device":
		device_type = camera.device_type.replace("type=", "").strip()
		serial_number = camera.serial_number.strip()
		sw_version = camera.software_information[0].replace("version=", "").strip()
		device_name = camera.machine_name.replace("name=", "").strip()

		return cls(
            name=device_name,
            model=device_type,
            serial_no=serial_number,
            sw_version=sw_version
        )