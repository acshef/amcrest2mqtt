from json import dumps
import logging
import os
import signal
import ssl
import sys
from threading import Timer
import typing as t

from amcrest import AmcrestCamera, AmcrestError
import paho.mqtt.client as mqtt

from .config import Config
from .const import *
from .device import Device
from .util import ping


_is_exiting = False # Global


logger = logging.getLogger(__name__)


class Amcrest2MQTT:
    mqtt_client: t.Optional[mqtt.Client] = None
    def __init__(self):
        self.config = Config.from_env()

    def run(self):
        # Exit if any of the required vars are not provided
        if self.config.amcrest_host is None:
            logger.error(f"Please set the {ENV_AMCREST_HOST} environment variable")
            sys.exit(1)

        if self.config.amcrest_password is None:
            logger.error(f"Please set the {ENV_AMCREST_PASSWORD} environment variable")
            sys.exit(1)

        if self.config.mqtt_username is None:
            logger.error(f"Please set the {ENV_MQTT_USERNAME} environment variable")
            sys.exit(1)

        from amcrest2mqtt import __version__ as version
        logger.info(f"{APP_NAME} v{version}")

        # Handle interruptions
        signal.signal(signal.SIGINT, self.signal_handler)

        self.camera = AmcrestCamera(
            self.config.amcrest_host,
            self.config.amcrest_port,
            self.config.amcrest_username,
            self.config.amcrest_password
        ).camera

        logger.info("Fetching camera details")

        try:
            device_type = self.camera.device_type.replace("type=", "").strip()
            serial_number = self.camera.serial_number.strip()
            sw_version = self.camera.software_information[0].replace("version=", "").strip()
            device_name = self.camera.machine_name.replace("name=", "").strip()
        except AmcrestError:
            logger.error(f"Error fetching camera details")
            self.exit_gracefully(1)

        self.device = Device(
            name=device_name,
            model=device_type,
            serial_no=serial_number,
            sw_version=sw_version
        )

        logger.info(f"Device: {self.device.manufacturer} {self.device.model} {self.device.name}")
        logger.info(f"Serial number: {self.device.serial_no}")
        logger.info(f"Software version: {self.device.sw_version}")

        a2m_topic_prefix = f"amcrest2mqtt/{self.device.serial_no}"
        node_id = f"amcrest2mqtt-{self.device.serial_no}"

        # MQTT topics
        self.topics = {
            # "config": f"amcrest2mqtt/{device.serial_no}/config",
            "status":               f"{a2m_topic_prefix}/status",
            "event":                f"{a2m_topic_prefix}/event",
            "motion":               f"{a2m_topic_prefix}/motion",
            "doorbell":             f"{a2m_topic_prefix}/doorbell",
            "human":                f"{a2m_topic_prefix}/human",
            "light":                f"{a2m_topic_prefix}/light",
            "storage_used":         f"{a2m_topic_prefix}/storage/used",
            "storage_used_percent": f"{a2m_topic_prefix}/storage/used_percent",
            "storage_total":        f"{a2m_topic_prefix}/storage/total",
            "home_assistant": {
                "doorbell":             f"{self.config.ha_prefix}/binary_sensor/{node_id}/{self.device.slug}_doorbell/config",
                "human":                f"{self.config.ha_prefix}/binary_sensor/{node_id}/{self.device.slug}_human/config",
                "motion":               f"{self.config.ha_prefix}/binary_sensor/{node_id}/{self.device.slug}_motion/config",
                "light":                f"{self.config.ha_prefix}/light/{node_id}/{self.device.slug}_light/config",
                "storage_used":         f"{self.config.ha_prefix}/sensor/{node_id}/{self.device.slug}_storage_used/config",
                "storage_used_percent": f"{self.config.ha_prefix}/sensor/{node_id}/{self.device.slug}_storage_used_percent/config",
                "storage_total":        f"{self.config.ha_prefix}/sensor/{node_id}/{self.device.slug}_storage_total/config",
            },
        }

        self.mqtt_client = mqtt.Client(
            client_id=f"amcrest2mqtt_{self.device.serial_no}", clean_session=False
        )
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.will_set(self.topics["status"], payload=PAYLOAD_OFFLINE, qos=self.config.mqtt_qos, retain=True)
        if self.config.mqtt_tls_enabled:
            logger.info(f"Setting up MQTT for TLS")
            if self.config.mqtt_tls_ca_cert is None:
                logger.error(f"Missing environment variable: {ENV_MQTT_TLS_CA_CERT}")
                sys.exit(1)
            if self.config.mqtt_tls_cert is None:
                logger.error(f"Missing environment variable: {ENV_MQTT_TLS_CERT}")
                sys.exit(1)
            if self.config.mqtt_tls_cert is None:
                logger.error(f"Missing environment variable: {ENV_MQTT_TLS_KEY}")
                sys.exit(1)
            self.mqtt_client.tls_set(
                ca_certs=self.config.mqtt_tls_ca_cert,
                certfile=self.config.mqtt_tls_cert,
                keyfile=self.config.mqtt_tls_key,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS,
            )
        else:
            self.mqtt_client.username_pw_set(
                username=self.config.mqtt_username,
                password=self.config.mqtt_password
            )

        try:
            self.mqtt_client.connect(self.config.mqtt_host, port=self.config.mqtt_port)
            self.mqtt_client.loop_start()
        except ConnectionError as error:
            logger.error(f"Could not connect to MQTT server: {error}")
            sys.exit(1)

        # Configure Home Assistant
        if self.config.ha_enabled:
            logger.info("Writing Home Assistant discovery config...")

            base_config = {
                "availability_topic": self.topics["status"],
                "device": self.device.as_mqtt_device_dict()
            }

            if self.is_doorbell:
                self.mqtt_publish(
                    self.topics["home_assistant"]["doorbell"],
                    base_config
                    | {
                        "state_topic": self.topics["doorbell"],
                        "payload_on": PAYLOAD_ON,
                        "payload_off": PAYLOAD_OFF,
                        "name": f"{device_name} Doorbell",
                        "unique_id": f"{self.device.serial_no}.doorbell",
                    },
                    json=True,
                )

            if self.is_ad410:
                self.mqtt_publish(
                    self.topics["home_assistant"]["human"],
                    base_config
                    | {
                        "state_topic": self.topics["human"],
                        "payload_on": PAYLOAD_ON,
                        "payload_off": PAYLOAD_OFF,
                        "device_class": "motion",
                        "name": f"{device_name} Human",
                        "unique_id": f"{self.device.serial_no}.human",
                        "icon": ICON_FACE_RECOGNITION,
                    },
                    json=True,
                )
                self.mqtt_publish(
                    self.topics["home_assistant"]["light"],
                    base_config
                    | {
                        "~": self.topics["light"],
                        "state_topic": "~/state",
                        "command_topic": "~/set",
                        "effect_command_topic": "~/set_effect",
                        "effect_state_topic": "~/effect",
                        "effect_list": [
                            LIGHT_MODE_SOLID,
                            LIGHT_MODE_STROBE
                        ],
                        "payload_on": PAYLOAD_ON,
                        "payload_off": PAYLOAD_OFF,
                        "name": f"{device_name} Flashlight",
                        "unique_id": f"{self.device.serial_no}.light",
                        "icon": ICON_FLASHLIGHT,
                    },
                    json=True
                )

            self.mqtt_publish(
                self.topics["home_assistant"]["motion"],
                base_config
                | {
                    "state_topic": self.topics["motion"],
                    "payload_on": PAYLOAD_ON,
                    "payload_off": PAYLOAD_OFF,
                    "device_class": "motion",
                    "name": f"{device_name} Motion",
                    "unique_id": f"{self.device.serial_no}.motion",
                },
                json=True,
            )

            if self.config.storage_poll_interval > 0:
                self.mqtt_publish(
                    self.topics["home_assistant"]["storage_used_percent"],
                    base_config
                    | {
                        "state_topic": self.topics["storage_used_percent"],
                        "unit_of_measurement": "%",
                        "icon": ICON_MICRO_SD,
                        "name": f"{device_name} Storage Used %",
                        "unique_id": f"{self.device.serial_no}.storage_used_percent",
                    },
                    json=True,
                )

                self.mqtt_publish(
                    self.topics["home_assistant"]["storage_used"],
                    base_config
                    | {
                        "state_topic": self.topics["storage_used"],
                        "unit_of_measurement": "GB",
                        "icon": ICON_MICRO_SD,
                        "name": f"{device_name} Storage Used",
                        "unique_id": f"{self.device.serial_no}.storage_used",
                    },
                    json=True,
                )

                self.mqtt_publish(
                    self.topics["home_assistant"]["storage_total"],
                    base_config
                    | {
                        "state_topic": self.topics["storage_total"],
                        "unit_of_measurement": "GB",
                        "icon": ICON_MICRO_SD,
                        "name": f"{device_name} Storage Total",
                        "unique_id": f"{self.device.serial_no}.storage_total",
                    },
                    json=True,
                )
        # Main loop
        self.mqtt_publish(self.topics["status"], PAYLOAD_ONLINE)
        # mqtt_publish(topics["config"], {
        #     "version": __version__,
        #     "device_type": device_type,
        #     "device_name": device_name,
        #     "sw_version": sw_version,
        #     "serial_number": serial_number,
        # }, json=True)

        if self.config.storage_poll_interval > 0:
            logger.info("Performing initial check of storage sensors...")
            self.refresh_storage_sensors()

        logger.info("Performing initial camera ping...")
        self.ping_camera()

        logger.info("Listening for events...")

        try:
            for code, payload in self.camera.event_actions("All", retries=5, timeout_cmd=(10.00, 3600)):
                if code == ("ProfileAlarmTransmit" if self.is_ad110 else "VideoMotion"):
                    motion_payload = PAYLOAD_ON if payload["action"] == "Start" else PAYLOAD_OFF
                    self.mqtt_publish(self.topics["motion"], motion_payload)
                elif code == "CrossRegionDetection" and payload["data"]["ObjectType"] == "Human":
                    human_payload = PAYLOAD_ON if payload["action"] == "Start" else PAYLOAD_OFF
                    self.mqtt_publish(self.topics["human"], human_payload)
                elif code == "_DoTalkAction_":
                    doorbell_payload = PAYLOAD_ON if payload["data"]["Action"] == "Invite" else PAYLOAD_OFF
                    self.mqtt_publish(self.topics["doorbell"], doorbell_payload)
                elif code == "LeFunctionStatusSync" and payload["data"]["Function"] == "WightLight":
                    light_payload = PAYLOAD_ON if payload["data"]["Status"] == "true" else PAYLOAD_OFF
                    light_mode = (
                        LIGHT_MODE_STROBE
                        if light_payload == PAYLOAD_ON and "true" in payload["data"]["Flicker"]
                        else LIGHT_MODE_SOLID
                    )
                    self.mqtt_publish("{}/{}".format(self.topics["light"], "state"), light_payload)
                    self.mqtt_publish("{}/{}".format(self.topics["light"], "effect"), light_mode)

                self.mqtt_publish(self.topics["event"], payload, json=True)
                logger.info(str(payload))

        except AmcrestError as error:
            logger.error(f"Amcrest error {error}")
            self.exit_gracefully(1)

    @property
    def is_ad110(self):
        assert self.device is not None
        return self.device.model == DEVICE_TYPE_AD110

    @property
    def is_ad410(self):
        assert self.device is not None
        return self.device.model == DEVICE_TYPE_AD410

    @property
    def is_doorbell(self):
        return self.is_ad110 or self.is_ad410

    def mqtt_publish(self, topic: str, payload: t.Any, exit_on_error=True, json=False):
        assert self.mqtt_client is not None

        msg = self.mqtt_client.publish(
            topic,
            payload=(dumps(payload) if json else payload),
            qos=self.config.mqtt_qos,
            retain=True
        )

        if msg.rc == mqtt.MQTT_ERR_SUCCESS:
            msg.wait_for_publish()
            return msg

        logger.error(f"Error publishing MQTT message: {mqtt.error_string(msg.rc)}")

        if exit_on_error:
            self.exit_gracefully(msg.rc, skip_mqtt=True)

    def on_mqtt_disconnect(self, client, userdata, rc: int):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection")
            self.exit_gracefully(rc, skip_mqtt=True)

    def exit_gracefully(self, rc: int, skip_mqtt=False):
        logger.info("Exiting app...")

        if self.mqtt_client is not None and self.mqtt_client.is_connected() and not skip_mqtt:
            self.mqtt_publish(self.topics["status"], PAYLOAD_OFFLINE, exit_on_error=False)
            self.mqtt_client.loop_stop(force=True)
            self.mqtt_client.disconnect()

        # Use os._exit instead of sys.exit to ensure an MQTT disconnect event causes the program to exit correctly
        # as they occur on a separate thread
        os._exit(rc)

    def refresh_storage_sensors(self):
        Timer(self.config.storage_poll_interval, self.refresh_storage_sensors).start()
        logger.info("Fetching storage sensors...")

        try:
            storage = self.camera.storage_all
            self.mqtt_publish(self.topics["storage_used_percent"], str(storage["used_percent"]))
            self.mqtt_publish(self.topics["storage_used"], str(storage["used"][0]))
            self.mqtt_publish(self.topics["storage_total"], str(storage["total"][0]))
        except AmcrestError as error:
            logger.warning(f"Error fetching storage information: {error}")

    def ping_camera(self):
        Timer(TIME_CAMERA_PING_INTERVAL, self.ping_camera).start()

        if not ping(self.config.amcrest_host, timeout=TIME_CAMERA_PING_TIMEOUT):
            logger.error("Ping unsuccessful")
            self.exit_gracefully(1)

    def signal_handler(self, sig, frame):
        # Exit immediately upon receiving a second SIGINT
        global _is_exiting

        if _is_exiting:
            os._exit(1)

        _is_exiting = True
        self.exit_gracefully(0)