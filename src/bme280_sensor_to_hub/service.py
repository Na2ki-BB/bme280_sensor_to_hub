import logging
import time

from .config import load_config
from .driver import BME280, BME280Error
from .writer import write_status

logger = logging.getLogger(__name__)


def _build_lines(temperature_c: float, humidity_pct: float, pressure_hpa: float) -> list[str]:
    now = time.strftime("%H:%M")
    return [
        f"BME280 {now}",
        f"Temp: {temperature_c:.1f}C",
        f"Humid: {humidity_pct:.1f}%",
        f"Press: {pressure_hpa:.0f}hPa",
    ]


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()

    with BME280(bus=config.i2c_bus, address=config.i2c_address) as sensor:
        while True:
            try:
                temperature_c, humidity_pct, pressure_hpa = sensor.read()
            except BME280Error:
                logger.exception("failed to read BME280, keeping previous status file")
            else:
                lines = _build_lines(temperature_c, humidity_pct, pressure_hpa)
                write_status(config.hub_data_dir, lines)

            time.sleep(config.poll_interval_sec)
