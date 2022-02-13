from typing import NamedTuple

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
            "via_device": self.via_device,
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
