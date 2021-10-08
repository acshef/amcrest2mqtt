from typing import NamedTuple

from slugify import slugify

from .const import *


class Device(NamedTuple):
	name: str
	model: str
	serial_no: str
	sw_version: str
	manufacturer = MANUFACTURER
	via_device = APP_NAME

	@property
	def slug(self):
		return slugify(self.name, separator="_")

	def as_mqtt_device_dict(self):
		return {
			"name": self.name,
			"manufacturer": self.manufacturer,
			"model": self.model,
			"identifiers": self.serial_no,
			"sw_version": self.sw_version,
			"via_device": self.via_device
		}