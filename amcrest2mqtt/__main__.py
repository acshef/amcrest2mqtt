from slugify import slugify
from amcrest import AmcrestCamera, AmcrestError
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
import os
import sys
from json import dumps
import signal
from threading import Timer
import ssl

from .const import *

__version__ = "2.0.0"

is_exiting = False
mqtt_client = None

# Read env variables
amcrest_host = os.getenv(ENV_AMCREST_HOST)
amcrest_port = int(os.getenv(ENV_AMCREST_PORT) or DEFAULT_AMCREST_PORT)
amcrest_username = os.getenv(ENV_AMCREST_USERNAME) or DEFAULT_AMCREST_USERNAME
amcrest_password = os.getenv(ENV_AMCREST_PASSWORD)
storage_poll_interval = int(os.getenv(ENV_STORAGE_POLL_INTERVAL) or DEFAULT_STORAGE_POLL_INTERVAL)

mqtt_host = os.getenv(ENV_MQTT_HOST) or DEFAULT_MQTT_HOST
mqtt_qos = int(os.getenv(ENV_MQTT_QOS) or DEFAULT_MQTT_QOS)
mqtt_port = int(os.getenv(ENV_MQTT_PORT) or DEFAULT_MQTT_PORT)
mqtt_username = os.getenv(ENV_MQTT_USERNAME)
mqtt_password = os.getenv(ENV_MQTT_PASSWORD)  # can be None
mqtt_tls_enabled = (os.getenv(ENV_MQTT_TLS_ENABLED) or "").lower() in ENV_ENABLED_VALUES
mqtt_tls_ca_cert = os.getenv(ENV_MQTT_TLS_CA_CERT)
mqtt_tls_cert = os.getenv(ENV_MQTT_TLS_CERT)
mqtt_tls_key = os.getenv(ENV_MQTT_TLS_KEY)

home_assistant = (os.getenv(ENV_HOME_ASSISTANT) or "").lower() in ENV_ENABLED_VALUES
home_assistant_prefix = os.getenv(ENV_HOME_ASSISTANT_PREFIX) or DEFAULT_HOME_ASSISTANT_PREFIX


# Helper functions and callbacks
def log(msg, level="INFO"):
    ts = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S")
    print(f"{ts} [{level}] {msg}")

def mqtt_publish(topic, payload, exit_on_error=True, json=False):
    global mqtt_client

    msg = mqtt_client.publish(
        topic, payload=(dumps(payload) if json else payload), qos=mqtt_qos, retain=True
    )

    if msg.rc == mqtt.MQTT_ERR_SUCCESS:
        msg.wait_for_publish()
        return msg

    log(f"Error publishing MQTT message: {mqtt.error_string(msg.rc)}", level="ERROR")

    if exit_on_error:
        exit_gracefully(msg.rc, skip_mqtt=True)

def on_mqtt_disconnect(client, userdata, rc):
    if rc != 0:
        log(f"Unexpected MQTT disconnection", level="ERROR")
        exit_gracefully(rc, skip_mqtt=True)

def exit_gracefully(rc, skip_mqtt=False):
    global topics, mqtt_client

    log("Exiting app...")

    if mqtt_client is not None and mqtt_client.is_connected() and skip_mqtt == False:
        mqtt_publish(topics["status"], "offline", exit_on_error=False)
        mqtt_client.loop_stop(force=True)
        mqtt_client.disconnect()

    # Use os._exit instead of sys.exit to ensure an MQTT disconnect event causes the program to exit correctly as they
    # occur on a separate thread
    os._exit(rc)

def refresh_storage_sensors():
    global camera, topics, storage_poll_interval

    Timer(storage_poll_interval, refresh_storage_sensors).start()
    log("Fetching storage sensors...")

    try:
        storage = camera.storage_all
        mqtt_publish(topics["storage_used_percent"], str(storage["used_percent"]))
        mqtt_publish(topics["storage_used"], str(storage["used"][0]))
        mqtt_publish(topics["storage_total"], str(storage["total"][0]))
    except AmcrestError as error:
        log(f"Error fetching storage information {error}", level="WARNING")

def ping_camera():
    Timer(30, ping_camera).start()
    response = os.system(f"ping -c1 -W100 {amcrest_host} >/dev/null 2>&1")

    if response != 0:
        log("Ping unsuccessful", level="ERROR")
        exit_gracefully(1)

def signal_handler(sig, frame):
    # exit immediately upon receiving a second SIGINT
    global is_exiting

    if is_exiting:
        os._exit(1)

    is_exiting = True
    exit_gracefully(0)

# Exit if any of the required vars are not provided
if amcrest_host is None:
    log("Please set the AMCREST_HOST environment variable", level="ERROR")
    sys.exit(1)

if amcrest_password is None:
    log("Please set the AMCREST_PASSWORD environment variable", level="ERROR")
    sys.exit(1)

if mqtt_username is None:
    log("Please set the MQTT_USERNAME environment variable", level="ERROR")
    sys.exit(1)


log(f"App Version: {__version__}")

# Handle interruptions
signal.signal(signal.SIGINT, signal_handler)

# Connect to camera
camera = AmcrestCamera(
    amcrest_host, amcrest_port, amcrest_username, amcrest_password
).camera

# Fetch camera details
log("Fetching camera details...")

try:
    device_type = camera.device_type.replace("type=", "").strip()
    is_ad110 = device_type == "AD110"
    is_ad410 = device_type == "AD410"
    is_doorbell = is_ad110 or is_ad410
    serial_number = camera.serial_number.strip()
    sw_version = camera.software_information[0].replace("version=", "").strip()
    device_name = camera.machine_name.replace("name=", "").strip()
    device_slug = slugify(device_name, separator="_")
except AmcrestError as error:
    log(f"Error fetching camera details", level="ERROR")
    exit_gracefully(1)

log(f"Device type: {device_type}")
log(f"Serial number: {serial_number}")
log(f"Software version: {sw_version}")
log(f"Device name: {device_name}")

# MQTT topics
topics = {
    "config": f"amcrest2mqtt/{serial_number}/config",
    "status": f"amcrest2mqtt/{serial_number}/status",
    "event": f"amcrest2mqtt/{serial_number}/event",
    "motion": f"amcrest2mqtt/{serial_number}/motion",
    "doorbell": f"amcrest2mqtt/{serial_number}/doorbell",
    "human": f"amcrest2mqtt/{serial_number}/human",
    "light": f"amcrest2mqtt/{serial_number}/light",
    "storage_used": f"amcrest2mqtt/{serial_number}/storage/used",
    "storage_used_percent": f"amcrest2mqtt/{serial_number}/storage/used_percent",
    "storage_total": f"amcrest2mqtt/{serial_number}/storage/total",
    "home_assistant": {
        "doorbell": f"{home_assistant_prefix}/binary_sensor/amcrest2mqtt-{serial_number}/{device_slug}_doorbell/config",
        "human": f"{home_assistant_prefix}/binary_sensor/amcrest2mqtt-{serial_number}/{device_slug}_human/config",
        "motion": f"{home_assistant_prefix}/binary_sensor/amcrest2mqtt-{serial_number}/{device_slug}_motion/config",
        "light": f"{home_assistant_prefix}/light/amcrest2mqtt-{serial_number}/{device_slug}_light/config",
        "storage_used": f"{home_assistant_prefix}/sensor/amcrest2mqtt-{serial_number}/{device_slug}_storage_used/config",
        "storage_used_percent": f"{home_assistant_prefix}/sensor/amcrest2mqtt-{serial_number}/{device_slug}_storage_used_percent/config",
        "storage_total": f"{home_assistant_prefix}/sensor/amcrest2mqtt-{serial_number}/{device_slug}_storage_total/config",
    },
}

# Connect to MQTT
mqtt_client = mqtt.Client(
    client_id=f"amcrest2mqtt_{serial_number}", clean_session=False
)
mqtt_client.on_disconnect = on_mqtt_disconnect
mqtt_client.will_set(topics["status"], payload="offline", qos=mqtt_qos, retain=True)
if mqtt_tls_enabled:
    log(f"Setting up MQTT for TLS")
    if mqtt_tls_ca_cert is None:
        log("Missing var: MQTT_TLS_CA_CERT", level="ERROR")
        sys.exit(1)
    if mqtt_tls_cert is None:
        log("Missing var: MQTT_TLS_CERT", level="ERROR")
        sys.exit(1)
    if mqtt_tls_cert is None:
        log("Missing var: MQTT_TLS_KEY", level="ERROR")
        sys.exit(1)
    mqtt_client.tls_set(
        ca_certs=mqtt_tls_ca_cert,
        certfile=mqtt_tls_cert,
        keyfile=mqtt_tls_key,
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS,
    )
else:
    mqtt_client.username_pw_set(mqtt_username, password=mqtt_password)

try:
    mqtt_client.connect(mqtt_host, port=mqtt_port)
    mqtt_client.loop_start()
except ConnectionError as error:
    log(f"Could not connect to MQTT server: {error}", level="ERROR")
    sys.exit(1)

# Configure Home Assistant
if home_assistant:
    log("Writing Home Assistant discovery config...")

    base_config = {
        "availability_topic": topics["status"],
        "qos": mqtt_qos,
        "device": {
            "name": f"Amcrest {device_type}",
            "manufacturer": "Amcrest",
            "model": device_type,
            "identifiers": serial_number,
            "sw_version": sw_version,
            "via_device": "amcrest2mqtt",
        },
    }

    if is_doorbell:
        mqtt_publish(
            topics["home_assistant"]["doorbell"],
            base_config
            | {
                "state_topic": topics["doorbell"],
                "payload_on": "on",
                "payload_off": "off",
                "name": f"{device_name} Doorbell",
                "unique_id": f"{serial_number}.doorbell",
            },
            json=True,
        )

    if is_ad410:
        mqtt_publish(
            topics["home_assistant"]["human"],
            base_config
            | {
                "state_topic": topics["human"],
                "payload_on": "on",
                "payload_off": "off",
                "device_class": "motion",
                "name": f"{device_name} Human",
                "unique_id": f"{serial_number}.human",
				"icon": "mdi:face-recognition",
            },
            json=True,
        )
        mqtt_publish(
            topics["home_assistant"]["light"],
            base_config
            | {
                "~": topics["light"],
                "state_topic": "~/state",
                "command_topic": "~/set",
				"effect_command_topic": "~/set_effect",
				"effect_state_topic": "~/effect",
				"effect_list": [
					"flashing"
				],
                "payload_on": "on",
                "payload_off": "off",
                "name": f"{device_name} Flashlight",
                "unique_id": f"{serial_number}.light",
				"icon": "mdi:flashlight",
            },
            json=True
        )

    mqtt_publish(
        topics["home_assistant"]["motion"],
        base_config
        | {
            "state_topic": topics["motion"],
            "payload_on": "on",
            "payload_off": "off",
            "device_class": "motion",
            "name": f"{device_name} Motion",
            "unique_id": f"{serial_number}.motion",
        },
        json=True,
    )

    if storage_poll_interval > 0:
        mqtt_publish(
            topics["home_assistant"]["storage_used_percent"],
            base_config
            | {
                "state_topic": topics["storage_used_percent"],
                "unit_of_measurement": "%",
                "icon": "mdi:micro-sd",
                "name": f"{device_name} Storage Used %",
                "unique_id": f"{serial_number}.storage_used_percent",
            },
            json=True,
        )

        mqtt_publish(
            topics["home_assistant"]["storage_used"],
            base_config
            | {
                "state_topic": topics["storage_used"],
                "unit_of_measurement": "GB",
                "icon": "mdi:micro-sd",
                "name": f"{device_name} Storage Used",
                "unique_id": f"{serial_number}.storage_used",
            },
            json=True,
        )

        mqtt_publish(
            topics["home_assistant"]["storage_total"],
            base_config
            | {
                "state_topic": topics["storage_total"],
                "unit_of_measurement": "GB",
                "icon": "mdi:micro-sd",
                "name": f"{device_name} Storage Total",
                "unique_id": f"{serial_number}.storage_total",
            },
            json=True,
        )

# Main loop
mqtt_publish(topics["status"], "online")
mqtt_publish(topics["config"], {
    "version": __version__,
    "device_type": device_type,
    "device_name": device_name,
    "sw_version": sw_version,
    "serial_number": serial_number,
}, json=True)

if storage_poll_interval > 0:
    refresh_storage_sensors()

ping_camera()

log("Listening for events...")

try:
    for code, payload in camera.event_actions("All", retries=5, timeout_cmd=(10.00, 3600)):
        if (is_ad110 and code == "ProfileAlarmTransmit") or (code == "VideoMotion" and not is_ad110):
            motion_payload = "on" if payload["action"] == "Start" else "off"
            mqtt_publish(topics["motion"], motion_payload)
        elif code == "CrossRegionDetection" and payload["data"]["ObjectType"] == "Human":
            human_payload = "on" if payload["action"] == "Start" else "off"
            mqtt_publish(topics["human"], human_payload)
        elif code == "_DoTalkAction_":
            doorbell_payload = "on" if payload["data"]["Action"] == "Invite" else "off"
            mqtt_publish(topics["doorbell"], doorbell_payload)
        elif code == "LeFunctionStatusSync" and payload["data"]["Function"] == "WightLight":
            light_payload = "on" if payload["data"]["Status"] == "true" else "off"
            effect = "flashing" if light_payload == "on" and "true" in payload["data"]["Flicker"] else ""
            mqtt_publish("{}/{}".format(topics["light"], "state"), light_payload)
            mqtt_publish("{}/{}".format(topics["light"], "effect"), effect)

        mqtt_publish(topics["event"], payload, json=True)
        log(str(payload))

except AmcrestError as error:
    log(f"Amcrest error {error}", level="ERROR")
    exit_gracefully(1)
