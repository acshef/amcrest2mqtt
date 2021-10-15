from os import getenv
from typing import NamedTuple, Optional

from .const import *


class Config(NamedTuple):
	amcrest_host: str
	amcrest_port: int
	amcrest_username: str
	amcrest_password: str
	storage_poll_interval: int

	mqtt_host: str
	mqtt_qos: int
	mqtt_port: int
	mqtt_username: str
	mqtt_password: Optional[str]
	mqtt_tls_enabled: bool
	mqtt_tls_ca_cert: str
	mqtt_tls_cert: str
	mqtt_tls_key: str

	ha_enabled: bool
	ha_prefix: str

	@classmethod
	def from_env(cls):
		return cls(
			amcrest_host=getenv(ENV_AMCREST_HOST),
			amcrest_port=int(getenv(ENV_AMCREST_PORT) or DEFAULT_AMCREST_PORT),
			amcrest_username=getenv(ENV_AMCREST_USERNAME) or DEFAULT_AMCREST_USERNAME,
			amcrest_password=getenv(ENV_AMCREST_PASSWORD),
			storage_poll_interval=int(getenv(ENV_STORAGE_POLL_INTERVAL) or DEFAULT_STORAGE_POLL_INTERVAL),
			mqtt_host=getenv(ENV_MQTT_HOST) or DEFAULT_MQTT_HOST,
			mqtt_qos=int(getenv(ENV_MQTT_QOS) or DEFAULT_MQTT_QOS),
			mqtt_port=int(getenv(ENV_MQTT_PORT) or DEFAULT_MQTT_PORT),
			mqtt_username=getenv(ENV_MQTT_USERNAME),
			mqtt_password=getenv(ENV_MQTT_PASSWORD),  # can be None
			mqtt_tls_enabled=get_boolenv(ENV_MQTT_TLS_ENABLED),
			mqtt_tls_ca_cert=getenv(ENV_MQTT_TLS_CA_CERT),
			mqtt_tls_cert=getenv(ENV_MQTT_TLS_CERT),
			mqtt_tls_key=getenv(ENV_MQTT_TLS_KEY),
			ha_enabled=get_boolenv(ENV_HOME_ASSISTANT),
			ha_prefix=getenv(ENV_HOME_ASSISTANT_PREFIX) or DEFAULT_HOME_ASSISTANT_PREFIX
		)

	@property
	def amcrest_camera_args(self):
		return (self.amcrest_host, self.amcrest_port, self.amcrest_username, self.amcrest_password)



def get_boolenv(key: str) -> bool:
	return (getenv(key) or "").strip().lower() in ENV_ENABLED_VALUES