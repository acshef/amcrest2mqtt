import logging
import os
import signal
import sys
from threading import Timer
import typing as t

from .camera import Camera, AmcrestError
from .config import Config
from .const import *
from .entity import Entity
from .mqtt_client import MQTTClient, MQTTMessage
from .util import clamp, ping


_is_exiting = False # Global


logger = logging.getLogger(__name__)


class Amcrest2MQTT:
    def __init__(self):
        self.config = Config.from_env()

    def run(self):
        from amcrest2mqtt import __version__
        logger.info(f"{APP_NAME} v{__version__}")

        # Exit if any of the required vars are not provided
        if self.config.amcrest_host is None:
            logger.error(f"Environment variable {ENV_AMCREST_HOST} must be set")
            sys.exit(1)

        if self.config.amcrest_password is None:
            logger.error(f"Environment variable {ENV_AMCREST_PASSWORD} must be set")
            sys.exit(1)

        if self.config.mqtt_username is None:
            logger.error(f"Environment variable {ENV_MQTT_USERNAME} must be set")
            sys.exit(1)

        # Handle interruptions
        signal.signal(signal.SIGINT, self.signal_handler)

        self.camera = Camera.from_config(self.config)

        logger.info("Fetching camera details")
        try:
            self.device = self.camera.get_device()
        except AmcrestError:
            logger.error(f"Error fetching camera details")
            sys.exit(1)

        logger.info(f"Device: {self.device.manufacturer} {self.device.model} {self.device.name}")
        logger.info(f"Serial number: {self.device.serial_no}")
        logger.info(f"Software version: {self.device.sw_version}")

        try:
            self.mqtt_client = MQTTClient(config=self.config, device=self.device)
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.on_message = self.on_mqtt_message
        except Exception as exc:
            logger.error(f"Could not connect to MQTT server: {exc}")
            sys.exit(1)

        # Create entities
        self.entity_doorbell = self.create_entity(**Entity.DEF_DOORBELL)
        self.entity_human = self.create_entity(**Entity.DEF_HUMAN)
        self.entity_flashlight = self.create_entity(**Entity.DEF_FLASHLIGHT)
        self.entity_motion = self.create_entity(**Entity.DEF_MOTION)
        self.entity_storage_used_percent = self.create_entity(**Entity.DEF_STORAGE_USED_PERCENT)
        self.entity_storage_used = self.create_entity(**Entity.DEF_STORAGE_USED)
        self.entity_storage_total = self.create_entity(**Entity.DEF_STORAGE_TOTAL)
        self.entity_siren_volume = self.create_entity(**Entity.DEF_SIREN_VOLUME)

        # Configure Home Assistant
        if self.config.ha_enabled:
            logger.info("Writing Home Assistant discovery config...")

            if self.is_doorbell:
                self.entity_doorbell.setup_ha()

            if self.is_ad410:
                self.entity_human.setup_ha()
                self.entity_flashlight.setup_ha()
                self.entity_siren_volume.setup_ha()

            self.entity_motion.setup_ha()

            if self.config.storage_poll_interval > 0:
                self.entity_storage_used_percent.setup_ha()
                self.entity_storage_used.setup_ha()
                self.entity_storage_total.setup_ha()

        # Begin main behavior
        self.mqtt_publish(self.device.status_topic, PAYLOAD_ONLINE)

        if self.config.config_poll_interval > 0:
            logger.info("Performing initial check of config sensors...")
            self.refresh_config_sensors()

        if self.config.storage_poll_interval > 0:
            logger.info("Performing initial check of storage sensors...")
            self.refresh_storage_sensors()

        logger.info("Performing initial camera ping...")
        self.ping_camera()

        if self.is_ad410:
            try:
                siren_volume = self.camera.get_config("VideoTalkPhoneGeneral.RingVolume", int)
                self.entity_siren_volume.publish(siren_volume)
            except:
                pass

        logger.info("Listening for events...")

        try:
            for code, payload in self.camera.events():
                self.handle_event(code, payload)
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

        try:
            return self.mqtt_client.publish(topic, payload, json)
        except Exception as exc:
            logger.exception(exc)
            if exit_on_error:
                self.exit_gracefully(1, skip_mqtt=True)

    def create_entity(self, name: str, component: str, *, friendly_name: str=None, **extra_config):
        return Entity(
            self,
            name,
            component,
            friendly_name=friendly_name,
            **extra_config
        )

    def on_mqtt_disconnect(self, client, userdata, rc: int):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection")
            self.exit_gracefully(rc, skip_mqtt=True)

    def on_mqtt_message(self, client, userdata, message: MQTTMessage):
        if self.is_ad410 and message.topic == self.entity_siren_volume.command_topics["command"]:
            new_volume = clamp(int(message.payload), min=0, max=100)
            logger.info(f"Setting Siren Volume to {new_volume}%")
            self.camera.set_config("VideoTalkPhoneGeneral.RingVolume", new_volume)
            siren_volume = self.camera.get_config("VideoTalkPhoneGeneral.RingVolume", int)
            self.entity_siren_volume.publish(siren_volume)
        else:
            logger.warning(f'Unsupported topic "{message.topic}"')

    def exit_gracefully(self, rc: int, skip_mqtt=False):
        logger.info("Exiting app...")

        if self.mqtt_client is not None and self.mqtt_client.is_connected() and not skip_mqtt:
            if self.device:
                self.mqtt_publish(self.device.status_topic, PAYLOAD_OFFLINE, exit_on_error=False)
            self.mqtt_client.loop_stop(force=True)
            self.mqtt_client.disconnect()

        # Use os._exit instead of sys.exit to ensure an MQTT disconnect event
        # causes the program to exit correctly as they occur on a separate thread
        os._exit(rc)

    def handle_event(self, code, payload):
        if code == ("ProfileAlarmTransmit" if self.is_ad110 else "VideoMotion"):
            motion_payload = PAYLOAD_ON if payload["action"] == "Start" else PAYLOAD_OFF
            self.entity_motion.publish(motion_payload)
        elif code == "CrossRegionDetection" and payload["data"]["ObjectType"] == "Human":
            human_payload = PAYLOAD_ON if payload["action"] == "Start" else PAYLOAD_OFF
            self.entity_human.publish(human_payload)
        elif code == "_DoTalkAction_":
            doorbell_payload = PAYLOAD_ON if payload["data"]["Action"] == "Invite" else PAYLOAD_OFF
            self.entity_doorbell.publish(doorbell_payload)
        elif code == "LeFunctionStatusSync" and payload["data"]["Function"] == "WightLight":
            light_payload = PAYLOAD_ON if payload["data"]["Status"] == "true" else PAYLOAD_OFF
            light_mode = (
                LIGHT_MODE_STROBE
                if light_payload == PAYLOAD_ON and "true" in payload["data"]["Flicker"]
                else LIGHT_MODE_SOLID
            )
            self.entity_flashlight.publish(light_payload)
            self.entity_flashlight.publish(light_mode, "effect")

        self.mqtt_publish(self.device.event_topic, payload, json=True)
        logger.info(str(payload))

    def refresh_config_sensors(self):
        Timer(self.config.config_poll_interval, self.refresh_config_sensors).start()
        logger.info("Fetching config sensors...")

        if self.is_ad410:
            siren_volume = self.camera.get_config("VideoTalkPhoneGeneral.RingVolume", int)
            self.entity_siren_volume.publish(siren_volume)

    def refresh_storage_sensors(self):
        Timer(self.config.storage_poll_interval, self.refresh_storage_sensors).start()
        logger.info("Fetching storage sensors...")

        try:
            storage = self.camera.storage_all
            self.entity_storage_used_percent.publish(storage["used_percent"])
            self.entity_storage_used.publish(storage["used"][0])
            self.entity_storage_total.publish(storage["total"][0])
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