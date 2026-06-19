import struct
import time
from dataclasses import dataclass

from smbus2 import SMBus

_REG_CALIB_1 = 0x88  # 24 bytes: dig_T1-T3, dig_P1-P9
_REG_DIG_H1 = 0xA1
_REG_CALIB_2 = 0xE1  # 7 bytes: dig_H2-H6 (packed)
_REG_CTRL_HUM = 0xF2
_REG_STATUS = 0xF3
_REG_CTRL_MEAS = 0xF4
_REG_DATA = 0xF7  # 8 bytes: pressure, temperature, humidity

_OVERSAMPLING_X1 = 0b001
_MODE_FORCED = 0b01
_STATUS_MEASURING = 0x08


class BME280Error(RuntimeError):
    pass


@dataclass(frozen=True)
class _Calibration:
    dig_T1: int
    dig_T2: int
    dig_T3: int
    dig_P1: int
    dig_P2: int
    dig_P3: int
    dig_P4: int
    dig_P5: int
    dig_P6: int
    dig_P7: int
    dig_P8: int
    dig_P9: int
    dig_H1: int
    dig_H2: int
    dig_H3: int
    dig_H4: int
    dig_H5: int
    dig_H6: int


def _to_int8(value: int) -> int:
    return value - 256 if value > 127 else value


class BME280:
    def __init__(self, bus: int, address: int):
        self._address = address
        self._bus = SMBus(bus)
        self._calibration = self._read_calibration()

    def close(self) -> None:
        self._bus.close()

    def __enter__(self) -> "BME280":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def read(self) -> tuple[float, float, float]:
        """Trigger a forced measurement, returns (temperature_c, humidity_pct, pressure_hpa)."""
        try:
            self._bus.write_byte_data(self._address, _REG_CTRL_HUM, _OVERSAMPLING_X1)
            self._bus.write_byte_data(
                self._address,
                _REG_CTRL_MEAS,
                (_OVERSAMPLING_X1 << 5) | (_OVERSAMPLING_X1 << 2) | _MODE_FORCED,
            )
            self._wait_until_measuring_done()
            data = self._bus.read_i2c_block_data(self._address, _REG_DATA, 8)
        except OSError as exc:
            raise BME280Error(f"I2C communication with BME280 failed: {exc}") from exc

        raw_pressure = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temperature = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_humidity = (data[6] << 8) | data[7]

        temperature_c, t_fine = self._compensate_temperature(raw_temperature)
        pressure_hpa = self._compensate_pressure(raw_pressure, t_fine)
        humidity_pct = self._compensate_humidity(raw_humidity, t_fine)

        return temperature_c, humidity_pct, pressure_hpa

    def _wait_until_measuring_done(self) -> None:
        for _ in range(20):
            status = self._bus.read_byte_data(self._address, _REG_STATUS)
            if not (status & _STATUS_MEASURING):
                return
            time.sleep(0.01)
        raise BME280Error("sensor did not finish measuring in time")

    def _read_calibration(self) -> _Calibration:
        # Split into two ≤16-byte reads to stay within the BCM2835 I2C FIFO size.
        calib_1 = (
            self._bus.read_i2c_block_data(self._address, _REG_CALIB_1, 16)
            + self._bus.read_i2c_block_data(self._address, _REG_CALIB_1 + 16, 8)
        )
        dig_h1 = self._bus.read_byte_data(self._address, _REG_DIG_H1)
        calib_2 = self._bus.read_i2c_block_data(self._address, _REG_CALIB_2, 7)

        (
            dig_t1,
            dig_t2,
            dig_t3,
            dig_p1,
            dig_p2,
            dig_p3,
            dig_p4,
            dig_p5,
            dig_p6,
            dig_p7,
            dig_p8,
            dig_p9,
        ) = struct.unpack("<HhhHhhhhhhhh", bytes(calib_1))

        dig_h2 = struct.unpack("<h", bytes(calib_2[0:2]))[0]
        dig_h3 = calib_2[2]
        dig_h4 = (_to_int8(calib_2[3]) * 16) | (calib_2[4] & 0x0F)
        dig_h5 = (_to_int8(calib_2[5]) * 16) | (calib_2[4] >> 4)
        dig_h6 = _to_int8(calib_2[6])

        return _Calibration(
            dig_T1=dig_t1,
            dig_T2=dig_t2,
            dig_T3=dig_t3,
            dig_P1=dig_p1,
            dig_P2=dig_p2,
            dig_P3=dig_p3,
            dig_P4=dig_p4,
            dig_P5=dig_p5,
            dig_P6=dig_p6,
            dig_P7=dig_p7,
            dig_P8=dig_p8,
            dig_P9=dig_p9,
            dig_H1=dig_h1,
            dig_H2=dig_h2,
            dig_H3=dig_h3,
            dig_H4=dig_h4,
            dig_H5=dig_h5,
            dig_H6=dig_h6,
        )

    def _compensate_temperature(self, adc_t: int) -> tuple[float, float]:
        calib = self._calibration
        var1 = (adc_t / 16384.0 - calib.dig_T1 / 1024.0) * calib.dig_T2
        var2 = ((adc_t / 131072.0 - calib.dig_T1 / 8192.0) ** 2) * calib.dig_T3
        t_fine = var1 + var2
        temperature_c = t_fine / 5120.0
        return temperature_c, t_fine

    def _compensate_pressure(self, adc_p: int, t_fine: float) -> float:
        calib = self._calibration
        var1 = t_fine / 2.0 - 64000.0
        var2 = var1 * var1 * calib.dig_P6 / 32768.0
        var2 = var2 + var1 * calib.dig_P5 * 2.0
        var2 = var2 / 4.0 + calib.dig_P4 * 65536.0
        var1 = (calib.dig_P3 * var1 * var1 / 524288.0 + calib.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * calib.dig_P1
        if var1 == 0:
            raise BME280Error("pressure compensation division by zero")

        pressure = 1048576.0 - adc_p
        pressure = (pressure - var2 / 4096.0) * 6250.0 / var1
        var1 = calib.dig_P9 * pressure * pressure / 2147483648.0
        var2 = pressure * calib.dig_P8 / 32768.0
        pressure = pressure + (var1 + var2 + calib.dig_P7) / 16.0
        return pressure / 100.0  # Pa -> hPa

    def _compensate_humidity(self, adc_h: int, t_fine: float) -> float:
        calib = self._calibration
        var_h = t_fine - 76800.0
        var_h = (adc_h - (calib.dig_H4 * 64.0 + calib.dig_H5 / 16384.0 * var_h)) * (
            calib.dig_H2
            / 65536.0
            * (
                1.0
                + calib.dig_H6
                / 67108864.0
                * var_h
                * (1.0 + calib.dig_H3 / 67108864.0 * var_h)
            )
        )
        var_h = var_h * (1.0 - calib.dig_H1 * var_h / 524288.0)
        return min(max(var_h, 0.0), 100.0)
