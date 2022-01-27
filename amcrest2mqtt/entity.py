from __future__ import annotations
import typing as t
import logging

from .config import Config
from .const import *
from .device import Device
from .util import slugify


if t.TYPE_CHECKING:
	from .amcrest2mqtt import Amcrest2MQTT


logger = logging.getLogger(__name__)


class Entity:
	def __init__(
		self,
		api: "Amcrest2MQTT",
		name: str,
		component: str,
		*,
		friendly_name: t.Optional[str] = None,
		command_topics: t.Optional[t.Dict[str, str]] = None,
		**extra_config
	):
		self.name = name
		self.component = component
		self.api = api
		self.__friendly_name = friendly_name
		self.command_topics: t.Dict[str, str] = {}
		self.extra_config = extra_config

		if command_topics:
			for command, topic in command_topics.items():
				self.extra_config[f"{command}_topic"] = topic
				self.command_topics[command] = self.absolute_topic(topic)

		if component in (COMPONENT_BINARY_SENSOR, COMPONENT_LIGHT, COMPONENT_SWITCH):
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

	def absolute_topic(self, topic: str):
		if topic.startswith("~"):
			topic = topic.replace("~", self.base_topic, 1)
		if topic.endswith("~"):
			start, _, _ = topic.rpartition("~") # Because there's no such thing as str.rreplace()
			topic = f"{start}{self.base_topic}"
		return topic

	def setup_ha(self):
		"""
		Publish discovery to Home Assistant, then subscribe to command topics
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
		for topic in self.command_topics.values():
			logger.info(f'Subscribing to command topic "{topic}" for entity "{self.name}"')
			self.api.mqtt_client.subscribe(topic)

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
		"command_topics": {
			"command": "~/set",
			"effect_command": "~/set_effect",
		},
		"effect_state_topic": "~/effect",
		"effect_list": [
			LIGHT_EFFECT_NONE,
			LIGHT_EFFECT_STROBE
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
	DEF_SIREN_VOLUME = {
		"name": "Siren Volume",
		"component": COMPONENT_NUMBER,
		"icon": ICON_VOLUME_HIGH,
		"command_topics": {
			"command": "~/set"
		},
		"min": 0,
		"max": 100,
		"step": 1,
	}
	DEF_WATERMARK = {
		"name": "Watermark",
		"component": COMPONENT_SWITCH,
		"icon": ICON_WATERMARK,
		"command_topics": {
			"command": "~/set"
		},
	}