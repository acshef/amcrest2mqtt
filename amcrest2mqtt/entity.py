from __future__ import annotations
import typing as t

from .config import Config
from .const import *
from .device import Device
from .util import slugify


if t.TYPE_CHECKING:
	from .amcrest2mqtt import Amcrest2MQTT


class Entity:
	def __init__(
		self,
		api: "Amcrest2MQTT",
		name: str,
		component: str,
		*,
		friendly_name: t.Optional[str] = None,
		**extra_config
	):
		self.name = name
		self.component = component
		self.api = api
		self.__friendly_name = friendly_name
		self.extra_config = extra_config

		if component in (COMPONENT_BINARY_SENSOR, COMPONENT_LIGHT):
			self.extra_config["payload_on"] = PAYLOAD_ON
			self.extra_config["payload_off"] = PAYLOAD_OFF

		if self.extra_config.get("device_class", False) is None:
			self.extra_config.pop("device_class")

	@property
	def config(self) -> Config:
		return self.api.config

	@property
	def device(self) -> Device:
		return self.api.device

	@property
	def friendly_name(self):
		"""
		The `friendly_name` arg if passed to ctor, otherwise `name`

		Will ALWAYS be prefixed with the device name
		"""
		name = self.__friendly_name or self.name
		return f"{self.device.name} {name}"

	@property
	def unique_id(self):
		return f"{self.device.serial_no}.{self.name_slug}"

	@property
	def name_slug(self):
		return slugify(self.name)

	@property
	def base_topic(self):
		return f"{self.device.topic}/{self.name_slug}"

	@property
	def config_topic(self):
		node_id = f"{APP_NAME}-{self.device.serial_no}"
		return f"{self.config.ha_prefix}/{self.component}/{node_id}/{self.device.slug}_{self.name_slug}/config"

	def discover(self):
		"""
		Publish discovery to Home Assistant
		"""
		self.api.mqtt_publish(
			self.config_topic,
			{
				"~": self.base_topic,
				"availability_topic": self.device.status_topic,
				"device": self.device.as_mqtt_device_dict(),
				"name": self.friendly_name,
				"state_topic": "~",
				"unique_id": self.unique_id,
				"qos": self.config.mqtt_qos,
				**self.extra_config,
			},
			json=True
		)

	def publish(self, payload: t.Any, topic: str = None, *, json: bool=False):
		"""
		Publish data to a topic relative to the `base_topic`, e.g.

		```
		topic="effect" -> f"{self.base_topic}/effect"
		```
		"""
		return self.api.mqtt_publish(
			self.base_topic + (f"/{topic}" if topic else ""),
			payload,
			json=json
		)

	DEF_DOORBELL = {
		"name": "Doorbell",
		"component": COMPONENT_BINARY_SENSOR
	}
	DEF_HUMAN = {
		"name": "Human",
		"component": COMPONENT_BINARY_SENSOR,
		"device_class": DEVICE_CLASS_MOTION,
		"icon": ICON_FACE_RECOGNITION
	}
	DEF_FLASHLIGHT = {
		"name": "Flashlight",
		"component": COMPONENT_LIGHT,
		"command_topic": "~/set",
		"effect_command_topic": "~/set_effect",
		"effect_state_topic": "~/effect",
		"effect_list": [
			LIGHT_MODE_SOLID,
			LIGHT_MODE_STROBE
		],
		"icon": ICON_FLASHLIGHT
	}
	DEF_MOTION = {
		"name": "Motion",
		"component": COMPONENT_BINARY_SENSOR,
		"device_class": DEVICE_CLASS_MOTION
	}
	DEF_STORAGE_USED_PERCENT = {
		"name": "Storage Used Percent",
		"component": COMPONENT_SENSOR,
		"friendly_name": "Storage Used %",
		"icon": ICON_MICRO_SD,
		"unit_of_measurement": UNITS_PERCENTAGE,
	}
	DEF_STORAGE_USED = {
		"name": "Storage Used",
		"component": COMPONENT_SENSOR,
		"icon": ICON_MICRO_SD,
		"unit_of_measurement": UNITS_GIGABYTES
	}
	DEF_STORAGE_TOTAL = {
		"name": "Storage Total",
		"component": COMPONENT_SENSOR,
		"icon": ICON_MICRO_SD,
		"unit_of_measurement": UNITS_GIGABYTES
	}