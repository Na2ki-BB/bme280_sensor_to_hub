from bme280_sensor_to_hub import service


def test_build_lines_formats_values(monkeypatch):
    monkeypatch.setattr(service.time, "strftime", lambda fmt: "12:34")

    lines = service._build_lines(23.4, 45.6, 1013.2)

    assert lines == [
        "BME280 12:34",
        "Temp: 23.4C",
        "Humid: 45.6%",
        "Press: 1013hPa",
    ]


def test_build_lines_returns_four_elements():
    lines = service._build_lines(0.0, 0.0, 0.0)

    assert len(lines) == 4
