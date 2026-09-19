"""Durable JSON storage outside the installation directory."""

import json
import os
import tempfile
import time
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
    """Persist JSON with Windows file-lock recovery.

    Uses atomic replacement when possible and retries transient Windows
    PermissionError cases before returning failure to the caller.
    """
    path = data_root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    last_error = None
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

        for attempt in range(3):
            try:
                os.replace(temporary, path)
                return value
            except PermissionError as error:
                last_error = error
                time.sleep(0.5 * (attempt + 1))

        if last_error:
            raise last_error
        return value
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")
