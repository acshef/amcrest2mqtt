from __future__ import annotations
from collections import deque
from functools import partial
import typing as t
import logging
import warnings

from .const import *
from .device import Device
from .util import slugify


if t.TYPE_CHECKING:
    from .amcrest2mqtt import Amcrest2MQTT


logger = logging.getLogger(__name__)


class Entity:
    def __init__(
        self,
        device: Device,
        name: str,
        component: str,
        *,
        friendly_name: t.Optional[str] = None,
        command_topics: t.Optional[t.Dict[str, str]] = None,
        **extra_config,
    ):
        self.name = name
        self.component = component
        self.device = device
        self._friendly_name = friendly_name
        self.command_topics: t.Dict[str, str] = {}
        self.extra_config = extra_config
        self._publish_callbacks: t.Deque["PublishCallback"] = deque()

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
    def friendly_name(self):
        """
        The `friendly_name` arg if passed to __init__, otherwise `name`

        Will ALWAYS be prefixed with the device name
        """
        name = self._friendly_name or self.name
        if name == "Doorbell" and self.device.name == "Doorbell":
            return name
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

    def get_ha_config_topic(self, prefix=DEFAULT_HOME_ASSISTANT_PREFIX):
        """
        https://www.home-assistant.io/docs/mqtt/discovery/#discovery-topic

        `<discovery_prefix>/<component>/[<node_id>/]<object_id>/config`

        |   |   |
        |---|---|
        | `<discovery_prefix>`   | The prefix for the discovery topic, `"homeassistant"` by default |
        | `<component>`          | One of the supported MQTT components, e.g. `binary_sensor`       |
        | `<node_id>` (Optional) | ID of the node providing the topic, this is not used by Home Assistant but may be used to structure the MQTT topic. The ID of the node must only consist of characters from the character class `[a-zA-Z0-9_-]` (alphanumerics, underscore and hyphen). |
        | `<object_id>`          | The ID of the device. This is only to allow for separate topics for each device and is not used for the entity_id. The ID of the device must only consist of characters from the character class `[a-zA-Z0-9_-]` (alphanumerics, underscore and hyphen). |
        """

        node_id = f"{APP_NAME}-{self.device.slug}-{self.device.serial_no}"
        object_id = self.name_slug

        return f"{prefix}/{self.component}/{node_id}/{object_id}/config"

    def absolute_topic(self, topic: str):
        if topic.startswith("~"):
            topic = topic.replace("~", self.base_topic, 1)
        if topic.endswith("~"):
            start, _, _ = topic.rpartition("~")  # Because there's no such thing as str.rreplace()
            topic = f"{start}{self.base_topic}"
        return topic

    def register_publish_callback(self, cb: PublishCallback, left=False):
        if left:
            self._publish_callbacks.appendleft(cb)
        else:
            self._publish_callbacks.append(cb)

    def setup_ha(self, api: "Amcrest2MQTT"):
        """
        Register publish callback, publish discovery to Home Assistant, then subscribe to command topics
        """

        callback = partial(self._publish_mqtt, api)
        self.register_publish_callback(callback)

        api.mqtt_publish(
            self.get_ha_config_topic(api.home_assistant_prefix),
            {
                "~": self.base_topic,
                "availability_topic": self.device.status_topic,
                "device": self.device.as_mqtt_device_dict(),
                "name": self.friendly_name,
                "state_topic": "~",
                "unique_id": self.unique_id,
                "qos": api.mqtt_qos,
                **self.extra_config,
            },
            json=True,
        )

        for topic in self.command_topics.values():
            logger.info(f'Subscribing to command topic "{topic}" for entity "{self.name}"')
            api.mqtt_client.subscribe(topic)

    def _publish_mqtt(self, api: "Amcrest2MQTT", payload: t.Any, topic: str = None):
        """
        Publish data to a topic relative to the `base_topic`, e.g.

        ```
        topic="effect" -> f"{self.base_topic}/effect"
        ```
        """
        full_topic = self.base_topic
        if topic:
            full_topic += f"/{topic}"
        api.mqtt_publish(full_topic, payload)

    def publish(self, payload: t.Any, topic: str = None):
        """
        Publish data to a topic relative to the `base_topic`, e.g.

        ```
        topic="effect" -> f"{self.base_topic}/effect"
        ```
        """
        if not len(self._publish_callbacks):
            warnings.warn(
                f'No publish callbacks registered for entity "{self.name}"',
                UselessPublishWarning,
                stacklevel=2,
            )
            return

        for cb in self._publish_callbacks:
            if cb(payload, topic) is False:
                break

    DEF_DOORBELL = {
        "name": "Doorbell",
        "component": COMPONENT_BINARY_SENSOR,
        "icon": ICON_RADIOBOX_MARKED,
    }
    DEF_HUMAN = {
        "name": "Human",
        "component": COMPONENT_BINARY_SENSOR,
        "device_class": DEVICE_CLASS_MOTION,
        "icon": ICON_FACE_RECOGNITION,
    }
    DEF_FLASHLIGHT = {
        "name": "Flashlight",
        "component": COMPONENT_LIGHT,
        "command_topics": {
            "command": "~/set",
            "effect_command": "~/set_effect",
        },
        "effect_state_topic": "~/effect",
        "effect_list": [LIGHT_EFFECT_NONE, LIGHT_EFFECT_STROBE],
        "icon": ICON_FLASHLIGHT,
    }
    DEF_MOTION = {
        "name": "Motion",
        "component": COMPONENT_BINARY_SENSOR,
        "device_class": DEVICE_CLASS_MOTION,
    }
    DEF_STORAGE_USED_PERCENT = {
        "name": "Storage Used Percent",
        "component": COMPONENT_SENSOR,
        "friendly_name": "Storage Used %",
        "icon": ICON_MICRO_SD,
        "unit_of_measurement": UNITS_PERCENTAGE,
        "entity_category": ENTITY_CATEGORY_DIAGNOSTIC,
    }
    DEF_STORAGE_USED = {
        "name": "Storage Used",
        "component": COMPONENT_SENSOR,
        "icon": ICON_MICRO_SD,
        "unit_of_measurement": UNITS_GIGABYTES,
        "entity_category": ENTITY_CATEGORY_DIAGNOSTIC,
    }
    DEF_STORAGE_TOTAL = {
        "name": "Storage Total",
        "component": COMPONENT_SENSOR,
        "icon": ICON_MICRO_SD,
        "unit_of_measurement": UNITS_GIGABYTES,
        "entity_category": ENTITY_CATEGORY_DIAGNOSTIC,
    }
    DEF_SIREN_VOLUME = {
        "name": "Siren Volume",
        "component": COMPONENT_NUMBER,
        "icon": ICON_VOLUME_HIGH,
        "command_topics": {"command": "~/set"},
        "entity_category": ENTITY_CATEGORY_CONFIG,
        "min": 0,
        "max": 100,
        "step": 1,
    }
    DEF_WATERMARK = {
        "name": "Watermark",
        "component": COMPONENT_SWITCH,
        "icon": ICON_WATERMARK,
        "command_topics": {"command": "~/set"},
        "entity_category": ENTITY_CATEGORY_CONFIG,
    }
    DEF_INDICATOR_LIGHT = {
        "name": "Indicator Light",
        "component": COMPONENT_LIGHT,
        "icon": ICON_CIRCLE_OUTLINE,
        "command_topics": {
            "command": "~/set",
        },
        "entity_category": ENTITY_CATEGORY_CONFIG,
    }


class PublishCallback(t.Protocol):
    def __call__(self, payload: t.Any, topic: t.Optional[str] = None) -> t.Any:
        """
        Return `False` to prevent the remainder of the callbacks from executing
        """
        ...


class UselessPublishWarning(Warning):
    pass
