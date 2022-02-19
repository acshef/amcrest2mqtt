# amcrest2mqtt

A simple app to expose all events generated by an Amcrest device to MQTT using the
[`python-amcrest`](https://github.com/tchellomello/python-amcrest) library.

It supports the following environment variables:

- `AMCREST_HOST` (required)
- `AMCREST_PORT` (optional, default = 80)
- `AMCREST_USERNAME` (optional, default = admin)
- `AMCREST_PASSWORD` (required)
- `DEVICE_NAME` (optional) - override the default device name used in the Amcrest app
- `MQTT_USERNAME` (required)
- `MQTT_PASSWORD` (optional, default = empty password)
- `MQTT_HOST` (optional, default = 'localhost')
- `MQTT_QOS` (optional, default = 0)
- `MQTT_PORT` (optional, default = 1883)
- `MQTT_TLS_CA_CERT` (required if using TLS) - path to the ca certs
- `MQTT_TLS_CERT` (required if using TLS) - path to the private cert
- `MQTT_TLS_KEY` (required if using TLS) - path to the private key
- `MQTT_CLIENT_SUFFIX` (optional, default = None) - an optional suffix to append to the MQTT Client ID to make it unique. Used when there are multiple `amcrest2mqtt` instances running for the _SAME_ Amcrest device
- `HOME_ASSISTANT_PREFIX` (optional, default = 'homeassistant') - enables Home Assistant entity discovery, set to '' to disable Home Assistant integration
- `STORAGE_POLL_INTERVAL` (optional, default = 3600) - how often to fetch storage data (in seconds)
- `CONFIG_POLL_INTERVAL` (optional, default = 60) - how often to fetch sensors based on config values (in seconds)

It exposes events to the following topics:

- `amcrest2mqtt/[SERIAL_NUMBER]/status` - availability - 'online' or 'offline'
- `amcrest2mqtt/[SERIAL_NUMBER]/event` - all events
- `amcrest2mqtt/[SERIAL_NUMBER]/config` - device configuration information
- `amcrest2mqtt/[SERIAL_NUMBER]/doorbell` - doorbell status (if AD110 or AD410) - 'off' or 'on'
- `amcrest2mqtt/[SERIAL_NUMBER]/flashlight` - doorbell flashlight (if AD410) - 'off' or 'on'
- `amcrest2mqtt/[SERIAL_NUMBER]/flashlight/effect` - doorbell flashlight _effect_ (if AD410) - 'None' or 'Strobe (30sec)'
- `amcrest2mqtt/[SERIAL_NUMBER]/human` - human detection (if AD410) - 'off' or 'on'
- `amcrest2mqtt/[SERIAL_NUMBER]/indicator_light` - colored ring around button (if AD410) - 'off' or 'on'
- `amcrest2mqtt/[SERIAL_NUMBER]/motion` - motion events (if supported)
- `amcrest2mqtt/[SERIAL_NUMBER]/siren_volume` - volume percentage (0-100) used for siren sound (if AD410)
- `amcrest2mqtt/[SERIAL_NUMBER]/storage_used_percent`
- `amcrest2mqtt/[SERIAL_NUMBER]/storage_used` - in GB
- `amcrest2mqtt/[SERIAL_NUMBER]/storage_total` - in GB
- `amcrest2mqtt/[SERIAL_NUMBER]/siren_volume` - volume percentage (0-100) used for siren sound (if AD410)
- `amcrest2mqtt/[SERIAL_NUMBER]/watermark` - Manufacturer watermark in corner of video (if AD410) - 'off' or 'on'

## Device Support

The app supports events for any Amcrest device supported by [`python-amcrest`](https://github.com/tchellomello/python-amcrest).

## Home Assistant

The app has built-in support for Home Assistant discovery, enabled by default. Set the `HOME_ASSISTANT_PREFIX` environment variable to `""` to disable support. If you are using a different MQTT prefix than the default, you will need to alter the `HOME_ASSISTANT_PREFIX` environment variable.

## Running the app

The easiest way to run the app is via Docker Compose, e.g.

```yaml
version: "3"
services:
  amcrest2mqtt:
    container_name: amcrest2mqtt
    image: acshef/amcrest2mqtt:latest
    restart: unless-stopped
    environment:
      AMCREST_HOST: 192.168.0.1
      AMCREST_PASSWORD: password
      MQTT_HOST: 192.168.0.2
      MQTT_USERNAME: admin
      MQTT_PASSWORD: password
```

## Out of Scope

### Multiple Devices

The app will not support multiple devices. You can run multiple instances of the app if you need to expose events for multiple devices.

### Non-Docker Environments

Docker is the only supported way of deploying the application. The app should run directly via Python but this is not supported.

### TO-DO

- Add more entities! :
  - Infrared/day/night mode
  - Video resolution
  - Video bitrate
  - Video framerate
  - Video sharpening
  - Snapshot resolution
  - Snapshot quality
  - Timestamp watermark
  - Doorbell sound
- Check if new AD410 entities are available for AD110
- Check if storage sensors are Gigabytes (GB) or Gibibytes (GiB)
- Explain command topics in readme
- Merge back into dchesterton's original repo

## Buy Me A ~~Coffee~~ Beer 🍻

A few people have kindly requested a way to donate a small amount of money. If you feel so inclined I've set up a "Buy Me A Coffee"
page where you can donate a small sum. Please do not feel obligated to donate in any way - I work on the app because it's
useful to myself and others, not for any financial gain - but any token of appreciation is much appreciated 🙂

<a href="https://www.buymeacoffee.com/dchesterton"><img src="https://img.buymeacoffee.com/api/?url=aHR0cHM6Ly9pbWcuYnV5bWVhY29mZmVlLmNvbS9hcGkvP25hbWU9ZGNoZXN0ZXJ0b24mc2l6ZT0zMDAmYmctaW1hZ2U9Ym1jJmJhY2tncm91bmQ9ZmY4MTNm&creator=dchesterton&is_creating=building%20software%20to%20help%20create%20awesome%20homes&design_code=1&design_color=%23ff813f&slug=dchesterton" height="240" /></a>
