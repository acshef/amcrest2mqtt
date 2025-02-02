import dataclasses
import logging
import os
import signal
import sys
from threading import Thread, Timer
import typing as t

from .camera import Camera, AmcrestError
from .const import *
from .entity import Entity
from .mqtt_client import MQTTClient, MQTTMessage
from .util import clamp, ping, str2bool


_is_exiting = False  # Global


logger = logging.getLogger(__name__)


@dataclasses.dataclass(init=True, repr=False, eq=False, order=False)
class Amcrest2MQTT:
    amcrest_host: str = MISSING
    amcrest_port: int = DEFAULT_AMCREST_PORT
    amcrest_username: str = DEFAULT_AMCREST_USERNAME
    amcrest_password: str = MISSING
    device_name: str = None
    storage_poll_interval: int = DEFAULT_STORAGE_POLL_INTERVAL
    config_poll_interval: int = DEFAULT_CONFIG_POLL_INTERVAL
    mqtt_host: str = DEFAULT_MQTT_HOST
    mqtt_qos: int = DEFAULT_MQTT_QOS
    mqtt_port: int = DEFAULT_MQTT_PORT
    mqtt_username: str = MISSING
    mqtt_password: t.Optional[str] = None
    mqtt_client_suffix: t.Optional[str] = None
    mqtt_tls_ca_cert: t.Optional[str] = None
    mqtt_tls_cert: t.Optional[str] = None
    mqtt_tls_key: t.Optional[str] = None
    home_assistant_prefix: t.Optional[str] = DEFAULT_HOME_ASSISTANT_PREFIX
    doorbell_off_timeout: float = DEFAULT_DOORBELL_OFF_TIMEOUT

    def __post_init__(self):
        if self.amcrest_host is MISSING:
            raise TypeError(f"{type(self).__qualname__}() requires str argument 'amcrest_host'")
        if self.amcrest_password is MISSING:
            raise TypeError(f"{type(self).__qualname__}() requires str argument 'amcrest_password'")
        if self.mqtt_username is MISSING:
            raise TypeError(f"{type(self).__qualname__}() requires str argument 'mqtt_username'")

    def run(self):
        from amcrest2mqtt import __version__

        logger.info(f"{APP_NAME} v{__version__}")

        # Handle interruptions
        signal.signal(signal.SIGINT, self.signal_handler)

        try:
            self.camera = Camera(
                host=self.amcrest_host,
                port=self.amcrest_port,
                username=self.amcrest_username,
                password=self.amcrest_password,
                device_name=self.device_name,
            )
        except Exception as exc:
            logger.error(f"Could not connect to Amcrest camera device: {exc}")
            sys.exit(1)

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
            self.mqtt_client = MQTTClient(
                host=self.mqtt_host,
                port=self.mqtt_port,
                username=self.mqtt_username,
                password=self.mqtt_password,
                qos=self.mqtt_qos,
                client_suffix=self.mqtt_client_suffix,
                tls_ca_cert=self.mqtt_tls_ca_cert,
                tls_cert=self.mqtt_tls_cert,
                tls_key=self.mqtt_tls_key,
                device=self.device,
            )
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
        self.entity_watermark = self.create_entity(**Entity.DEF_WATERMARK)
        self.entity_indicator_light = self.create_entity(**Entity.DEF_INDICATOR_LIGHT)

        self.doorbell_off_timer: t.Optional[Timer] = None

        # Configure Home Assistant
        if self.home_assistant_prefix:
            logger.info("Writing Home Assistant discovery config...")

            if self.is_doorbell:
                self.entity_doorbell.setup_ha(self)

            if self.is_ad410:
                self.entity_human.setup_ha(self)
                self.entity_flashlight.setup_ha(self)
                self.entity_siren_volume.setup_ha(self)
                self.entity_watermark.setup_ha(self)
                self.entity_indicator_light.setup_ha(self)

            self.entity_motion.setup_ha(self)

            if self.storage_poll_interval > 0:
                self.entity_storage_used_percent.setup_ha(self)
                self.entity_storage_used.setup_ha(self)
                self.entity_storage_total.setup_ha(self)

        # Begin main behavior
        self.mqtt_publish(self.device.status_topic, PAYLOAD_ONLINE)

        # Not used by Home Assistant -- for purely MQTT-based uses
        self.mqtt_publish(
            self.device.config_topic,
            {"version": __version__, **self.device.as_mqtt_device_dict()},
            json=True,
        )

        if self.config_poll_interval > 0:
            self.refresh_config_sensors(initial=True)

        if self.storage_poll_interval > 0:
            self.refresh_storage_sensors(initial=True)

        logger.info("Performing initial camera ping...")
        self.ping_camera()

        logger.info("Entering infinite loop; listening for events...")

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

    def create_entity(
        self,
        name: str,
        component: str,
        *,
        friendly_name: str = None,
        **extra_config,
    ):
        return Entity(self.device, name, component, friendly_name=friendly_name, **extra_config)

    def on_mqtt_disconnect(self, client, userdata, rc: int):
        if rc != 0:
            logger.error(f"Unexpected MQTT disconnection")
            self.exit_gracefully(rc, skip_mqtt=True)

    def on_mqtt_message(self, client, userdata, message: MQTTMessage):
        handler_thread = Thread(
            target=self.handle_mqtt_message,
            args=(message.topic, message.payload.decode()),
            daemon=True,
        )
        handler_thread.start()

    def exit_gracefully(self, rc: int, skip_mqtt=False):
        logger.info("Exiting app...")

        if self.mqtt_client is not None and self.mqtt_client.is_connected() and not skip_mqtt:
            if self.device:
                self.mqtt_publish(
                    self.device.status_topic,
                    PAYLOAD_OFFLINE,
                    exit_on_error=False,
                )
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
            if doorbell_payload == PAYLOAD_ON:
                if self.doorbell_off_timeout:
                    self.doorbell_off_timer = Timer(self.doorbell_off_timeout, self._send_doorbell_off).start()
            else:
                if self.doorbell_off_timer is not None:
                    self.doorbell_off_timer.cancel()
        elif code == "LeFunctionStatusSync" and payload["data"]["Function"] == "WightLight":
            light_payload = PAYLOAD_ON if payload["data"]["Status"] == "true" else PAYLOAD_OFF
            light_mode = (
                LIGHT_EFFECT_STROBE if "true" in payload["data"]["Flicker"] else LIGHT_EFFECT_NONE
            )
            self.entity_flashlight.publish(light_payload)
            self.entity_flashlight.publish(light_mode, "effect")

        self.mqtt_publish(self.device.event_topic, payload, json=True)
        logger.info(str(payload))

    def handle_mqtt_message(self, topic: str, payload: str):
        if self.is_ad410 and topic == self.entity_indicator_light.command_topics["command"]:
            logger.info(f"Setting Indicator Light to {payload}")
            self.camera.set_config({CONFIG_INDICATOR_LIGHT: payload == PAYLOAD_ON})
            self._refresh_config_indicator_light()
        elif self.is_ad410 and topic == self.entity_watermark.command_topics["command"]:
            logger.info(f"Setting Watermark to {payload}")
            self.camera.set_config({CONFIG_WATERMARK: payload == PAYLOAD_ON})
            self._refresh_config_watermark()
        elif self.is_ad410 and topic == self.entity_siren_volume.command_topics["command"]:
            new_volume = clamp(int(payload), min=0, max=100)
            logger.info(f"Setting Siren Volume to {new_volume}%")
            self.camera.set_config({CONFIG_SIREN_VOLUME: new_volume})
            self._refresh_config_siren_volume()
        elif self.is_ad410 and topic == self.entity_flashlight.command_topics["command"]:
            if payload == PAYLOAD_ON:
                logger.info(f"Setting Flashlight to {payload}")
                self.camera.set_config({CONFIG_LIGHT_MODE: "ForceOn", CONFIG_LIGHT_STATE: "On"})
                self.entity_flashlight.publish(PAYLOAD_ON)
                self.entity_flashlight.publish(LIGHT_EFFECT_NONE, "effect")
            elif payload == PAYLOAD_OFF:
                logger.info(f"Setting Flashlight to {payload}")
                self.camera.set_config({CONFIG_LIGHT_MODE: "Off"})
                self.entity_flashlight.publish(PAYLOAD_OFF)
            else:
                logger.warning(f"Unknown Flashlight payload {payload}")
        elif self.is_ad410 and topic == self.entity_flashlight.command_topics["effect_command"]:
            set_config_state = None
            if payload == LIGHT_EFFECT_NONE:
                set_config_state = "On"
            elif payload == LIGHT_EFFECT_STROBE:
                set_config_state = "Flicker"

            if set_config_state:
                logger.info(f"Setting Flashlight mode to {payload}")
                self.camera.set_config(
                    {
                        CONFIG_LIGHT_MODE: "ForceOn",
                        CONFIG_LIGHT_STATE: set_config_state,
                    }
                )
                self.entity_flashlight.publish(payload, "effect")
            else:
                logger.warning(f"Unknown Flashlight effect payload {payload}")
        else:
            logger.warning(f'Received message at unsupported command topic "{topic}"')

    def _refresh_config_siren_volume(self):
        siren_volume = self.camera.get_config(CONFIG_SIREN_VOLUME, int)
        self.entity_siren_volume.publish(siren_volume)

    def _refresh_config_watermark(self):
        watermark_is_enabled = self.camera.get_config(CONFIG_WATERMARK, str2bool)
        self.entity_watermark.publish(PAYLOAD_ON if watermark_is_enabled else PAYLOAD_OFF)

    def _refresh_config_indicator_light(self):
        indicator_light_is_enabled = self.camera.get_config(CONFIG_INDICATOR_LIGHT, str2bool)
        self.entity_indicator_light.publish(
            PAYLOAD_ON if indicator_light_is_enabled else PAYLOAD_OFF
        )

    def _send_doorbell_off(self):
        logger.info(f"Didn't receive doorbell off message within {self.doorbell_off_timeout:.1f} sec")
        self.entity_doorbell.publish(PAYLOAD_OFF)
        self.doorbell_off_timer = None

    def refresh_config_sensors(self, initial=False):
        Timer(self.config_poll_interval, self.refresh_config_sensors).start()
        if initial:
            logger.info("Performing initial fetch of config sensors...")
        else:
            logger.info("Fetching config sensors...")

        if self.is_ad410:
            self._refresh_config_siren_volume()
            self._refresh_config_watermark()
            self._refresh_config_indicator_light()

    def refresh_storage_sensors(self, initial=False):
        Timer(self.storage_poll_interval, self.refresh_storage_sensors).start()
        if initial:
            logger.info("Performing initial fetch of storage sensors...")
        else:
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

        if not ping(self.amcrest_host, timeout=TIME_CAMERA_PING_TIMEOUT):
            logger.error("Ping unsuccessful")
            self.exit_gracefully(1)

    def signal_handler(self, sig, frame):
        # Exit immediately upon receiving a second SIGINT
        global _is_exiting

        if _is_exiting:
            os._exit(1)

        _is_exiting = True
        self.exit_gracefully(0)
