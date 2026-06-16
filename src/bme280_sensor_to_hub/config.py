import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    hub_data_dir: str
    poll_interval_sec: float
    i2c_bus: int
    i2c_address: int


def _parse_env(name: str, default: str, parse):
    value = os.environ.get(name, default)
    try:
        return parse(value)
    except ValueError as exc:
        raise ConfigError(f"invalid value for {name}: {value!r}") from exc


def load_config() -> Config:
    hub_data_dir = os.environ.get("BME280_HUB_DATA_DIR")
    if not hub_data_dir:
        raise ConfigError("BME280_HUB_DATA_DIR is required")

    poll_interval_sec = _parse_env("BME280_POLL_INTERVAL_SEC", "60", float)
    i2c_bus = _parse_env("BME280_I2C_BUS", "1", int)
    i2c_address = _parse_env("BME280_I2C_ADDRESS", "0x76", lambda v: int(v, 0))

    return Config(
        hub_data_dir=hub_data_dir,
        poll_interval_sec=poll_interval_sec,
        i2c_bus=i2c_bus,
        i2c_address=i2c_address,
    )
