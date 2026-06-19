import struct

import pytest

from bme280_sensor_to_hub import driver
from bme280_sensor_to_hub.driver import BME280, BME280Error

_ADDRESS = 0x76

_CALIB = {
    "T1": 27504,
    "T2": 26435,
    "T3": -1000,
    "P1": 36477,
    "P2": -10685,
    "P3": 3024,
    "P4": 2855,
    "P5": 140,
    "P6": -7,
    "P7": 15500,
    "P8": -14600,
    "P9": 6000,
    "H1": 75,
    "H2": 355,
    "H3": 0,
    "H4": 320,  # chosen as a multiple of 16 to keep byte-packing simple
    "H5": 0,
    "H6": 30,
}

_ADC_T = 519888
_ADC_P = 415148
_ADC_H = 24747


def _expected_compensation(adc_t, adc_p, adc_h, calib):
    """Independent re-implementation of the Bosch compensation formulas,
    used as the test's expected value so the test doesn't just call back
    into the code under test."""
    var1 = (adc_t / 16384.0 - calib["T1"] / 1024.0) * calib["T2"]
    var2 = ((adc_t / 131072.0 - calib["T1"] / 8192.0) ** 2) * calib["T3"]
    t_fine = var1 + var2
    temperature_c = t_fine / 5120.0

    var1 = t_fine / 2.0 - 64000.0
    var2 = var1 * var1 * calib["P6"] / 32768.0
    var2 = var2 + var1 * calib["P5"] * 2.0
    var2 = var2 / 4.0 + calib["P4"] * 65536.0
    var1 = (calib["P3"] * var1 * var1 / 524288.0 + calib["P2"] * var1) / 524288.0
    var1 = (1.0 + var1 / 32768.0) * calib["P1"]
    pressure = 1048576.0 - adc_p
    pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
    var1 = calib["P9"] * pressure * pressure / 2147483648.0
    var2 = pressure * calib["P8"] / 32768.0
    pressure = pressure + (var1 + var2 + calib["P7"]) / 16.0
    pressure_hpa = pressure / 100.0

    var_h = t_fine - 76800.0
    var_h = (adc_h - (calib["H4"] * 64.0 + calib["H5"] / 16384.0 * var_h)) * (
        calib["H2"]
        / 65536.0
        * (1.0 + calib["H6"] / 67108864.0 * var_h * (1.0 + calib["H3"] / 67108864.0 * var_h))
    )
    humidity_pct = var_h * (1.0 - calib["H1"] * var_h / 524288.0)

    return temperature_c, humidity_pct, pressure_hpa


def _pack_20bit(value: int) -> bytes:
    msb = (value >> 12) & 0xFF
    lsb = (value >> 4) & 0xFF
    xlsb = (value & 0x0F) << 4
    return bytes([msb, lsb, xlsb])


def _build_registers(calib: dict, adc_t: int, adc_p: int, adc_h: int) -> dict:
    registers = {}

    calib_1 = struct.pack(
        "<HhhHhhhhhhhh",
        calib["T1"], calib["T2"], calib["T3"],
        calib["P1"], calib["P2"], calib["P3"], calib["P4"],
        calib["P5"], calib["P6"], calib["P7"], calib["P8"], calib["P9"],
    )
    for offset, byte in enumerate(calib_1):
        registers[driver._REG_CALIB_1 + offset] = byte

    registers[driver._REG_DIG_H1] = calib["H1"]

    # dig_H4/H5 are split across nibbles; H5 % 16 == 0 and H4 % 16 == 0 here,
    # which keeps the low/high nibble cross-terms zero and the packing simple.
    e4 = (calib["H4"] >> 4) & 0xFF
    e5 = ((calib["H5"] >> 4) & 0xF0) | (calib["H4"] & 0x0F)
    e6 = (calib["H5"] >> 4) & 0xFF
    calib_2 = bytes([
        calib["H2"] & 0xFF, (calib["H2"] >> 8) & 0xFF,
        calib["H3"] & 0xFF,
        e4,
        e5,
        e6,
        calib["H6"] & 0xFF,
    ])
    for offset, byte in enumerate(calib_2):
        registers[driver._REG_CALIB_2 + offset] = byte

    registers[driver._REG_STATUS] = 0x00  # not measuring

    data = _pack_20bit(adc_p) + _pack_20bit(adc_t) + bytes([(adc_h >> 8) & 0xFF, adc_h & 0xFF])
    for offset, byte in enumerate(data):
        registers[driver._REG_DATA + offset] = byte

    return registers


class _FakeSMBus:
    def __init__(self, registers: dict):
        self._registers = dict(registers)
        self.writes = []
        self.closed = False

    def read_byte_data(self, address, register):
        assert address == _ADDRESS
        return self._registers[register]

    def read_i2c_block_data(self, address, register, length):
        assert address == _ADDRESS
        return [self._registers[register + i] for i in range(length)]

    def write_byte_data(self, address, register, value):
        assert address == _ADDRESS
        self.writes.append((register, value))
        self._registers[register] = value

    def close(self):
        self.closed = True


def test_read_returns_compensated_values(monkeypatch):
    registers = _build_registers(_CALIB, _ADC_T, _ADC_P, _ADC_H)
    fake_bus = _FakeSMBus(registers)
    monkeypatch.setattr(driver, "SMBus", lambda bus: fake_bus)

    sensor = BME280(bus=1, address=_ADDRESS)
    temperature_c, humidity_pct, pressure_hpa = sensor.read()

    expected_temperature, expected_humidity, expected_pressure = _expected_compensation(
        _ADC_T, _ADC_P, _ADC_H, _CALIB
    )
    assert temperature_c == pytest.approx(expected_temperature)
    assert humidity_pct == pytest.approx(expected_humidity)
    assert pressure_hpa == pytest.approx(expected_pressure)


def test_read_triggers_forced_mode_measurement(monkeypatch):
    registers = _build_registers(_CALIB, _ADC_T, _ADC_P, _ADC_H)
    fake_bus = _FakeSMBus(registers)
    monkeypatch.setattr(driver, "SMBus", lambda bus: fake_bus)

    sensor = BME280(bus=1, address=_ADDRESS)
    fake_bus.writes.clear()  # drop any setup writes before the measurement we're checking
    sensor.read()

    assert fake_bus.writes == [
        (driver._REG_CTRL_HUM, driver._OVERSAMPLING_X1),
        (
            driver._REG_CTRL_MEAS,
            (driver._OVERSAMPLING_X1 << 5) | (driver._OVERSAMPLING_X1 << 2) | driver._MODE_FORCED,
        ),
    ]


def test_read_wraps_i2c_errors_in_bme280error(monkeypatch):
    registers = _build_registers(_CALIB, _ADC_T, _ADC_P, _ADC_H)
    fake_bus = _FakeSMBus(registers)
    monkeypatch.setattr(driver, "SMBus", lambda bus: fake_bus)

    sensor = BME280(bus=1, address=_ADDRESS)

    def _raise(*args, **kwargs):
        raise OSError("simulated I2C failure")

    monkeypatch.setattr(fake_bus, "read_byte_data", _raise)

    with pytest.raises(BME280Error):
        sensor.read()


def test_close_closes_underlying_bus(monkeypatch):
    registers = _build_registers(_CALIB, _ADC_T, _ADC_P, _ADC_H)
    fake_bus = _FakeSMBus(registers)
    monkeypatch.setattr(driver, "SMBus", lambda bus: fake_bus)

    with BME280(bus=1, address=_ADDRESS):
        pass

    assert fake_bus.closed
