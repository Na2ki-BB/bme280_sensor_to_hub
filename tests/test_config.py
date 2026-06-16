import pytest

from bme280_sensor_to_hub.config import ConfigError, load_config


def test_load_config_requires_hub_data_dir(monkeypatch):
    monkeypatch.delenv("BME280_HUB_DATA_DIR", raising=False)

    with pytest.raises(ConfigError):
        load_config()


def test_load_config_uses_defaults(monkeypatch):
    monkeypatch.setenv("BME280_HUB_DATA_DIR", "/tmp/hub")
    monkeypatch.delenv("BME280_POLL_INTERVAL_SEC", raising=False)
    monkeypatch.delenv("BME280_I2C_BUS", raising=False)
    monkeypatch.delenv("BME280_I2C_ADDRESS", raising=False)

    config = load_config()

    assert config.hub_data_dir == "/tmp/hub"
    assert config.poll_interval_sec == 60
    assert config.i2c_bus == 1
    assert config.i2c_address == 0x76


def test_load_config_reads_overrides(monkeypatch):
    monkeypatch.setenv("BME280_HUB_DATA_DIR", "/tmp/hub")
    monkeypatch.setenv("BME280_POLL_INTERVAL_SEC", "10")
    monkeypatch.setenv("BME280_I2C_BUS", "2")
    monkeypatch.setenv("BME280_I2C_ADDRESS", "0x77")

    config = load_config()

    assert config.poll_interval_sec == 10
    assert config.i2c_bus == 2
    assert config.i2c_address == 0x77


def test_load_config_rejects_invalid_poll_interval(monkeypatch):
    monkeypatch.setenv("BME280_HUB_DATA_DIR", "/tmp/hub")
    monkeypatch.setenv("BME280_POLL_INTERVAL_SEC", "not-a-number")

    with pytest.raises(ConfigError):
        load_config()
