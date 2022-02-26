import argparse, logging, os

from .amcrest2mqtt import Amcrest2MQTT
from .const import *


class CustomArgumentParser(argparse.ArgumentParser):
    def _add_action(self, action: argparse.Action):
        env_name = action.dest.upper()
        if env_name in os.environ:
            action.default = os.getenv(env_name)
            action.required = False
        return super()._add_action(action)


def main():
    parser = CustomArgumentParser()
    parser.add_argument("--device-name", metavar="S", type=str)
    parser.add_argument("--amcrest-host", metavar="S", required=True, type=str)
    parser.add_argument("--amcrest-port", metavar="N", default=DEFAULT_AMCREST_PORT, type=int)
    parser.add_argument(
        "--amcrest-username", metavar="S", default=DEFAULT_AMCREST_USERNAME, type=str
    )
    parser.add_argument("--amcrest-password", metavar="S", required=True, type=str)
    parser.add_argument(
        "--storage-poll-interval",
        metavar="N",
        help="Number of seconds between checks for storage sensors/entities; 0 to disable",
        default=DEFAULT_STORAGE_POLL_INTERVAL,
        type=int,
    )
    parser.add_argument(
        "--config-poll-interval",
        metavar="N",
        help="Number of seconds between checks for sensors/entities based on camera config table; 0 to disable",
        default=DEFAULT_CONFIG_POLL_INTERVAL,
        type=int,
    )
    parser.add_argument("--mqtt-host", metavar="S", default=DEFAULT_MQTT_HOST, type=str)
    parser.add_argument("--mqtt-qos", metavar="N", default=DEFAULT_MQTT_QOS, type=int)
    parser.add_argument("--mqtt-port", metavar="N", default=DEFAULT_MQTT_PORT, type=int)
    parser.add_argument("--mqtt-username", metavar="S", required=True, type=str)
    parser.add_argument("--mqtt-password", metavar="S", type=str)
    parser.add_argument(
        "--mqtt-client-suffix",
        metavar="S",
        help="An optional suffix to append to the MQTT Client ID to make it unique. Used when there are multiple amcrest2mqtt instances running for the *SAME* Amcrest device",
        type=str,
    )
    parser.add_argument("--mqtt-tls-ca-cert", metavar="PATH", type=str)
    parser.add_argument("--mqtt-tls-cert", metavar="PATH", type=str)
    parser.add_argument("--mqtt-tls-key", metavar="PATH", type=str)
    parser.add_argument(
        "--home-assistant-prefix",
        metavar="S",
        help='The prefix for the Home Assistant\'s MQTT discovery topic(s), see <https://www.home-assistant.io/docs/mqtt/discovery/#discovery_prefix>; "" to disable Home Assistant integration',
        default=DEFAULT_HOME_ASSISTANT_PREFIX,
        type=str,
    )

    logging.basicConfig(
        level=logging.INFO,
        datefmt="%d/%m/%Y %H:%M:%S",
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logging.captureWarnings(True)

    args = vars(parser.parse_args())
    app = Amcrest2MQTT(**args)
    app.run()


if __name__ == "__main__":
    main()
