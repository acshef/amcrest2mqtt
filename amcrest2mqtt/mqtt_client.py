import logging, ssl, sys
from json import dumps
import typing as t

import paho.mqtt.client as mqtt

from .config import Config
from .const import *
from .device import Device

logger = logging.getLogger(__name__)

class MQTTPublishError(Exception):
    pass

class MQTTClient:
    def __init__(self, config: Config, device: Device):
        self.config = config
        self.device = device

        self.client = mqtt.Client(
            client_id=f"{APP_NAME}_{device.serial_no}", clean_session=False
        )
        self.client.will_set(
            device.status_topic,
            payload=PAYLOAD_OFFLINE,
            qos=config.mqtt_qos,
            retain=True
        )

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

    def publish(self, topic: str, payload: t.Any, json=False) -> mqtt.MQTTMessage:
        msg = self.client.publish(
            topic,
            payload=dumps(payload) if json else str(payload),
            qos=self.config.mqtt_qos,
            retain=True
        )

        if msg.rc == mqtt.MQTT_ERR_SUCCESS:
            msg.wait_for_publish()
            return msg

        raise MQTTPublishError(f"Error publishing MQTT message: {mqtt.error_string(msg.rc)}")