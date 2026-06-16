import json
from datetime import datetime

from bme280_sensor_to_hub.writer import write_status


def test_write_status_writes_expected_json(tmp_path):
    write_status(str(tmp_path), ["a", "b", "c", "d"])

    written = json.loads((tmp_path / "bme280.json").read_text())

    assert written["lines"] == ["a", "b", "c", "d"]
    datetime.fromisoformat(written["updated_at"])  # raises if not parseable


def test_write_status_leaves_no_temp_files(tmp_path):
    write_status(str(tmp_path), ["a", "b", "c", "d"])

    assert [p.name for p in tmp_path.iterdir()] == ["bme280.json"]


def test_write_status_overwrites_existing_file(tmp_path):
    write_status(str(tmp_path), ["1", "2", "3", "4"])
    write_status(str(tmp_path), ["5", "6", "7", "8"])

    written = json.loads((tmp_path / "bme280.json").read_text())

    assert written["lines"] == ["5", "6", "7", "8"]
