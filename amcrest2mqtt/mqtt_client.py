import logging, ssl, sys
from json import dumps
import typing as t

from paho.mqtt.client import Client, MQTTMessage, MQTT_ERR_SUCCESS, error_string

from .const import *
from .device import Device

__all__ = ["MQTTClient", "MQTTMessage", "MQTTPublishError"]


logger = logging.getLogger(__name__)


class MQTTPublishError(Exception):
    pass


class MQTTClient:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: t.Optional[str] = None,
        *,
        qos: int = DEFAULT_MQTT_QOS,
        client_suffix: t.Optional[str] = None,
        tls_ca_cert: t.Optional[str] = None,
        tls_cert: t.Optional[str] = None,
        tls_key: t.Optional[str] = None,
        device: Device,
    ):
        self.device = device
        self.client_suffix = client_suffix
        self.qos = qos
        self.client = Client(client_id=self.client_id, clean_session=False)
        self.client.will_set(device.status_topic, payload=PAYLOAD_OFFLINE, qos=qos, retain=True)

        if tls_ca_cert or tls_cert or tls_key:
            self.client.tls_set(
                ca_certs=tls_ca_cert,
                certfile=tls_cert,
                keyfile=tls_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
            )
        else:
            self.client.username_pw_set(username=username, password=password)

        self.client.connect(host, port=port)
        self.client.loop_start()

    def __getattr__(self, attr):
        return getattr(self.client, attr)

    @property
    def client_id(self):
        id_ = f"{APP_NAME}_{self.device.serial_no}"
        if self.client_suffix:
            id_ = f"{id_}_{self.client_suffix}"
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
