APP_NAME = "amcrest2mqtt"
MANUFACTURER = "Amcrest"

ENV_AMCREST_HOST = "AMCREST_HOST"
ENV_AMCREST_PORT = "AMCREST_PORT"
ENV_AMCREST_USERNAME = "AMCREST_USERNAME"
ENV_AMCREST_PASSWORD = "AMCREST_PASSWORD"
ENV_STORAGE_POLL_INTERVAL = "STORAGE_POLL_INTERVAL"
ENV_CONFIG_POLL_INTERVAL = "SETTINGS_POLL_INTERVAL"
ENV_MQTT_HOST = "MQTT_HOST"
ENV_MQTT_QOS = "MQTT_QOS"
ENV_MQTT_PORT = "MQTT_PORT"
ENV_MQTT_USERNAME = "MQTT_USERNAME"
ENV_MQTT_PASSWORD = "MQTT_PASSWORD"
ENV_MQTT_CLIENT_SUFFIX = "MQTT_CLIENT_SUFFIX"
ENV_MQTT_TLS_ENABLED = "MQTT_TLS_ENABLED"
ENV_MQTT_TLS_CA_CERT = "MQTT_TLS_CA_CERT"
ENV_MQTT_TLS_CERT = "MQTT_TLS_CERT"
ENV_MQTT_TLS_KEY = "MQTT_TLS_KEY"
ENV_HOME_ASSISTANT = "HOME_ASSISTANT"
ENV_HOME_ASSISTANT_PREFIX = "HOME_ASSISTANT_PREFIX"

CAMERA_EVENTS_SPECIFIER = "All"
CAMERA_EVENTS_RETRIES = 5
CAMERA_EVENTS_TIMEOUT = (10.00, 3600) # (connect timeout, read timeout)

DEFAULT_AMCREST_PORT = 80
DEFAULT_AMCREST_USERNAME = "admin"
DEFAULT_STORAGE_POLL_INTERVAL = 3600
DEFAULT_CONFIG_POLL_INTERVAL = 60
DEFAULT_MQTT_HOST = "localhost"
DEFAULT_MQTT_QOS = 0
DEFAULT_MQTT_PORT = 1883
DEFAULT_HOME_ASSISTANT_PREFIX = "homeassistant"
ENV_ENABLED_VALUES = {"true", "1", "y", "yes", "on"}

DEVICE_CLASS_MOTION = "motion"

DEVICE_TYPE_AD110 = "AD110"
DEVICE_TYPE_AD410 = "AD410"

COMPONENT_BINARY_SENSOR = "binary_sensor"
COMPONENT_LIGHT = "light"
COMPONENT_NUMBER = "number"
COMPONENT_SENSOR = "sensor"
COMPONENT_SWITCH = "switch"

ICON_FACE_RECOGNITION = "mdi:face-recognition"
ICON_FLASHLIGHT = "mdi:flashlight"
ICON_MICRO_SD = "mdi:micro-sd"
ICON_VOLUME_HIGH = "mdi:volume-high"
ICON_WATERMARK = "mdi:watermark"

LIGHT_EFFECT_NONE = "None"
LIGHT_EFFECT_STROBE = "Strobe (30sec)"

PAYLOAD_ON = "on"
PAYLOAD_OFF = "off"
PAYLOAD_ONLINE = "online"
PAYLOAD_OFFLINE = "offline"

TIME_CAMERA_PING_INTERVAL = 30 # Seconds
TIME_CAMERA_PING_TIMEOUT = 100 # Seconds

UNITS_PERCENTAGE = "%"
UNITS_GIGABYTES = "GB"

CONFIG_SIREN_VOLUME = "VideoTalkPhoneGeneral.RingVolume"
CONFIG_LIGHT_MODE = "Lighting_V2[0][0][1].Mode"
CONFIG_LIGHT_STATE = "Lighting_V2[0][0][1].State"
CONFIG_WATERMARK = "VideoWidget[0].PictureTitle.EncodeBlend"