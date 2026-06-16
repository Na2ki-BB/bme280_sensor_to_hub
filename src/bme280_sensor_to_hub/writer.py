import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

def write_status(data_dir: str, lines: list[str]) -> None:
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "lines": lines,
    }

    target_path = Path(data_dir) / "bme280.json"

    fd, tmp_path_str = tempfile.mkstemp(dir=data_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file)
        os.replace(tmp_path_str, target_path)
    except Exception:
        os.remove(tmp_path_str)
        raise