import logging
from amcrest2mqtt import Amcrest2MQTT

logging.basicConfig(
	level=logging.INFO,
	datefmt="%d/%m/%Y %H:%M:%S",
	format='%(asctime)s [%(levelname)s] %(message)s'
)

app = Amcrest2MQTT()
app.run()