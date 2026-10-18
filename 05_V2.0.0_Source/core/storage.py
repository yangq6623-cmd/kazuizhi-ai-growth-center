"""Durable JSON storage outside the installation directory."""

import json
import os
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path


# Serialize local JSON I/O so dashboard polling and background workers cannot race atomic replacements on Windows.
_JSON_IO_LOCK = threading.RLock()


def data_root():
    base = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    root = base / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def read_json(relative_path, default):
    path = data_root() / relative_path
    with _JSON_IO_LOCK:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default


def read_json_snapshot(relative_path, default):
    """Read an atomically-written ledger without the process-wide writer lock.

    Owner read-only snapshots must not be blocked behind long Windows os.replace
    retries. All authoritative mutations continue to use write_json/read_json.
    A missing or temporarily unavailable file returns the caller's default.
    """
    path = data_root() / relative_path
    for attempt in range(2):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return default
        except (OSError, ValueError) as error:
            if attempt == 0:
                time.sleep(0.005)
                continue
            # An existing but unreadable/corrupt authoritative ledger must
            # never turn into a fabricated zero-count owner snapshot.
            raise OSError(f"snapshot_unavailable: {relative_path}") from error
    return default


def write_json(relative_path, value):
    """Persist JSON with serialized Windows file-lock recovery."""
    path = data_root() / relative_path
    with _JSON_IO_LOCK:
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

            for attempt in range(8):
                try:
                    os.replace(temporary, path)
                    return value
                except PermissionError as error:
                    last_error = error
                    time.sleep(min(1.5, 0.15 * (attempt + 1)))

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
