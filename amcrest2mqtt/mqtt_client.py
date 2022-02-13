import logging, ssl, sys
from json import dumps
import typing as t

from paho.mqtt.client import Client, MQTTMessage, MQTT_ERR_SUCCESS, error_string

from .config import Config
from .const import *
from .device import Device

__all__ = ["MQTTClient", "MQTTMessage", "MQTTPublishError"]


logger = logging.getLogger(__name__)


class MQTTPublishError(Exception):
    pass


class MQTTClient:
    def __init__(self, config: Config, device: Device):
        self.config = config
        self.device = device
        self.client = Client(client_id=self.client_id, clean_session=False)
        self.client.will_set(device.status_topic, payload=PAYLOAD_OFFLINE, qos=config.mqtt_qos, retain=True)

        if config.mqtt_tls_enabled:
            logger.info(f"Setting up MQTT for TLS")
            if config.mqtt_tls_ca_cert is None:
                logger.error(f"When MQTT TLS is enabled, environment variable {ENV_MQTT_TLS_CA_CERT} must be set")
                sys.exit(1)
            if config.mqtt_tls_cert is None:
                logger.error(f"When MQTT TLS is enabled, environment variable {ENV_MQTT_TLS_CERT} must be set")
                sys.exit(1)
            if config.mqtt_tls_cert is None:
                logger.error(f"When MQTT TLS is enabled, environment variable {ENV_MQTT_TLS_KEY} must be set")
                sys.exit(1)
            self.client.tls_set(
                ca_certs=config.mqtt_tls_ca_cert,
                certfile=config.mqtt_tls_cert,
                keyfile=config.mqtt_tls_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
            )
        else:
            self.client.username_pw_set(
                username=config.mqtt_username,
                password=config.mqtt_password
            )

        self.client.connect(config.mqtt_host, port=config.mqtt_port)
        self.client.loop_start()

    def __getattr__(self, attr):
        return getattr(self.client, attr)

    @property
    def client_id(self):
        id_ = f"{APP_NAME}_{self.device.serial_no}"
        if self.config.mqtt_client_suffix:
            id_ = f"{id_}_{self.config.mqtt_client_suffix}"
        return id_

    @property
    def on_message(self):
        return self.client.on_message

    @on_message.setter
    def on_message(self, on_message):
        self.client.on_message = on_message

    @property
    def on_disconnect(self):
        return self.client.on_disconnect

    @on_disconnect.setter
    def on_disconnect(self, on_disconnect):
        self.client.on_disconnect = on_disconnect

    def publish(self, topic: str, payload: t.Any, json=False) -> MQTTMessage:
        msg = self.client.publish(
            topic, self.transform_payload(payload, json), qos=self.qos, retain=True
        )

        if msg.rc == MQTT_ERR_SUCCESS:
            msg.wait_for_publish()
            return msg

        raise MQTTPublishError(f"Error publishing MQTT message: {error_string(msg.rc)}")

    @staticmethod
    def transform_payload(payload: t.Any, json: bool) -> str:
        if json:
            return dumps(payload)
        if isinstance(payload, bytes):
            return payload.decode()
        return str(payload)
