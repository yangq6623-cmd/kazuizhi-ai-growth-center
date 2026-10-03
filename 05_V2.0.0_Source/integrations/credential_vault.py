"""Local credential vault interface for R8-12.

Sensitive OAuth tokens never enter GitHub, Mission JSON, account registry or
normal logs. On Windows they are protected with the current user's DPAPI key and
stored as opaque binary blobs under LocalAppData.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

from core.storage import data_root


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _vault_dir() -> Path:
    path = data_root() / "r8_12" / "credentials"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(key: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(key or "").strip())
    if not text:
        raise ValueError("credential key cannot be empty")
    return text[:180]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _protect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("secure credential storage currently requires Windows DPAPI")
    in_blob, keepalive = _blob(data)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Kazuizhi R8-12 Credential".encode("utf-16-le"),
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("Windows DPAPI encryption failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        del keepalive


def _unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("secure credential storage currently requires Windows DPAPI")
    in_blob, keepalive = _blob(data)
    out_blob = DATA_BLOB()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0x01,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError("Windows DPAPI decryption failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        del keepalive


def put_secret(key: str, value: str) -> None:
    raw = str(value or "").encode("utf-8")
    if not raw:
        raise ValueError("secret value cannot be empty")
    path = _vault_dir() / f"{_safe_name(key)}.bin"
    protected = _protect(raw)
    path.write_bytes(protected)


def get_secret(key: str) -> str | None:
    path = _vault_dir() / f"{_safe_name(key)}.bin"
    if not path.is_file():
        return None
    return _unprotect(path.read_bytes()).decode("utf-8")


def delete_secret(key: str) -> bool:
    path = _vault_dir() / f"{_safe_name(key)}.bin"
    if not path.exists():
        return False
    path.unlink()
    return True


def status() -> dict:
    return {
        "backend": "windows_dpapi" if os.name == "nt" else "unsupported",
        "secrets_in_registry": False,
        "secrets_in_github": False,
        "storage": "LocalAppData opaque DPAPI blobs",
    }
