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
    """Atomically persist JSON in the user-data directory.

    The temporary file is created beside the destination, flushed and fsynced,
    then replaced atomically. This keeps an interrupted write from leaving a
    half-written JSON document that would look like lost user data on restart.
    """
    path = data_root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
    return value


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")
