"""Durable JSON storage outside the installation directory."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def data_root():
    base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    root = base / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_json(relative_path, default):
    path = data_root() / relative_path
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(relative_path, value):
    path = data_root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return value


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")

