"""R8-01 Android single-device adapter backed by the local ADB executable.

This module is deliberately truthful: a phone is connected only when the local
ADB process reports state ``device``. It never fabricates device, account or
screen state and it never attempts to bypass Android/platform verification.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from core.storage import now_iso, read_json, write_json
from core.r8_control import control_status, record_device_probe, register_device

AUDIT_PATH = "r8/device_audit.json"
RUNTIME_PATH = "r8/device_runtime.json"
TRANSFER_DIR = "/sdcard/Download/Kazuizhi"
MAX_AUDIT = 500


def _candidate_adb_paths():
    candidates = []
    configured = str(os.environ.get("KAZUIZHI_ADB_PATH") or "").strip()
    if configured:
        p = Path(configured).expanduser()
        candidates.append(p / "adb.exe" if p.is_dir() else p)
    for command in ("adb", "adb.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    home = Path.home()
    candidates.extend([
        home / "platform-tools" / "adb.exe",
        home / "ADB" / "platform-tools" / "adb.exe",
        Path("C:/platform-tools/adb.exe"),
    ])
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        candidates.append(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
    seen = set()
    for item in candidates:
        key = str(item).lower()
        if key not in seen:
            seen.add(key)
            yield item


def find_adb():
    for path in _candidate_adb_paths():
        try:
            if path.is_file():
                return str(path.resolve())
        except OSError:
            continue
    return None


def _run(args, timeout=8, binary=False):
    adb = find_adb()
    if not adb:
        raise RuntimeError("未找到 Android Platform Tools / adb.exe")
    command = [adb] + list(args)
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        text=not binary,
        encoding=None if binary else "utf-8",
        errors=None if binary else "replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        error = result.stderr if not binary else result.stderr.decode("utf-8", "replace")
        raise RuntimeError((error or "ADB 命令执行失败").strip()[:500])
    return result.stdout


def _parse_devices_output(text):
    devices = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("list of devices") or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        attrs = {}
        for part in parts[2:]:
            if ":" in part:
                key, value = part.split(":", 1)
                attrs[key] = value
        devices.append({
            "device_id": serial,
            "state": state,
            "model_hint": attrs.get("model"),
            "product": attrs.get("product"),
            "transport_id": attrs.get("transport_id"),
        })
    return devices


def _parse_battery_output(text):
    match = re.search(r"(?m)^\s*level:\s*(\d+)\s*$", str(text or ""))
    return int(match.group(1)) if match else None


def _parse_screen_size(text):
    match = re.search(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", str(text or ""))
    if not match:
        return None
    return {"width": int(match.group(1)), "height": int(match.group(2))}


def _parse_awake(text):
    value = str(text or "")
    if re.search(r"mWakefulness=Awake|Display Power: state=ON", value):
        return True
    if re.search(r"mWakefulness=(?:Asleep|Dozing)|Display Power: state=OFF", value):
        return False
    return None


def _shell(device_id, *args, timeout=8):
    return _run(["-s", device_id, "shell", *args], timeout=timeout)


def _device_details(device):
    device_id = device["device_id"]
    if device.get("state") != "device":
        return dict(device, connected=False, screen_awake=None)

    def prop(name):
        try:
            return _shell(device_id, "getprop", name).strip()
        except RuntimeError:
            return ""

    try:
        battery = _parse_battery_output(_shell(device_id, "dumpsys", "battery"))
    except RuntimeError:
        battery = None
    try:
        screen = _parse_screen_size(_shell(device_id, "wm", "size"))
    except RuntimeError:
        screen = None
    try:
        awake = _parse_awake(_shell(device_id, "dumpsys", "power"))
    except RuntimeError:
        awake = None
    model = prop("ro.product.model") or device.get("model_hint") or "Android"
    return dict(
        device,
        connected=True,
        model=model,
        manufacturer=prop("ro.product.manufacturer"),
        android_version=prop("ro.build.version.release"),
        sdk=prop("ro.build.version.sdk"),
        battery=battery,
        screen=screen,
        screen_awake=awake,
    )


def _runtime_state():
    state = read_json(RUNTIME_PATH, None)
    if not isinstance(state, dict):
        state = {"devices": {}, "updated_at": now_iso()}
        write_json(RUNTIME_PATH, state)
    return state


def _save_runtime(state):
    state["updated_at"] = now_iso()
    write_json(RUNTIME_PATH, state)
    return state


def _append_audit(event):
    data = read_json(AUDIT_PATH, None)
    if not isinstance(data, dict):
        data = {"events": []}
    event = dict(event or {})
    event.setdefault("at", now_iso())
    data["events"] = (data.get("events") or [])[-(MAX_AUDIT - 1):] + [event]
    write_json(AUDIT_PATH, data)
    return event


def device_audit(limit=80):
    data = read_json(AUDIT_PATH, None)
    events = (data or {}).get("events") if isinstance(data, dict) else []
    return {"items": list(events or [])[-max(1, min(int(limit), MAX_AUDIT)):], "total": len(events or [])}


def _record_connection_transition(runtime_device, device_id, new_state):
    old_state = runtime_device.get("connection")
    if old_state and old_state != new_state:
        _append_audit({
            "device_id": device_id,
            "action": "device_connected" if new_state == "connected" else "device_disconnected",
            "actor": "system",
            "result": "ok",
        })
    runtime_device["connection"] = new_state
    runtime_device["updated_at"] = now_iso()


def scan_and_sync():
    adb = find_adb()
    if not adb:
        return {
            "adb": {"found": False, "path": None, "status": "missing"},
            "devices": [],
            "pilot": {"limit": 1, "connected": 0},
            "message": "未找到 adb.exe；请安装 Android Platform Tools 或设置 KAZUIZHI_ADB_PATH。",
        }
    try:
        output = _run(["devices", "-l"], timeout=10)
        raw_devices = _parse_devices_output(output)
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        return {
            "adb": {"found": True, "path": adb, "status": "error"},
            "devices": [],
            "pilot": {"limit": 1, "connected": 0},
            "message": str(error),
        }

    devices = [_device_details(item) for item in raw_devices]
    connected = [item for item in devices if item.get("connected")]
    control = control_status()
    registered = list(control.get("devices") or [])
    registered_ids = {item.get("device_id") for item in registered}

    primary = connected[0] if connected else None
    blocked = connected[1:]
    if primary:
        try:
            if primary["device_id"] not in registered_ids:
                register_device({
                    "device_id": primary["device_id"],
                    "label": primary.get("model") or "Android 真机",
                    "device_type": "real_android",
                    "transport": "usb",
                })
            record_device_probe(
                primary["device_id"], True, source="adb",
                detail=f"model={primary.get('model') or ''}; android={primary.get('android_version') or ''}",
            )
        except ValueError as error:
            primary["control_sync_error"] = str(error)

    current_connected_ids = {item["device_id"] for item in connected}
    for item in registered:
        device_id = item.get("device_id")
        if device_id and device_id not in current_connected_ids:
            try:
                record_device_probe(device_id, False, source="adb", detail="ADB 当前未发现该设备")
            except ValueError:
                pass

    runtime = _runtime_state()
    modes = runtime.setdefault("devices", {})
    all_known_ids = {item.get("device_id") for item in devices} | {item.get("device_id") for item in registered}
    for device_id in [value for value in all_known_ids if value]:
        entry = modes.setdefault(device_id, {"mode": "r8", "updated_at": now_iso()})
        _record_connection_transition(entry, device_id, "connected" if device_id in current_connected_ids else "disconnected")
    _save_runtime(runtime)

    control = control_status()
    control_devices = {item.get("device_id"): item for item in control.get("devices", [])}
    accounts = list(control.get("accounts") or [])
    for item in devices:
        entry = modes.setdefault(item["device_id"], {"mode": "r8", "updated_at": now_iso()})
        item["control_mode"] = entry.get("mode", "r8")
        item["current_task"] = entry.get("current_task")
        registered_device = control_devices.get(item["device_id"]) or {}
        item["risk_level"] = registered_device.get("risk_level", "unknown")
        account = next((x for x in accounts if x.get("device_id") == item["device_id"]), None)
        item["platform"] = account.get("platform_name") if account else None
        item["account"] = account.get("alias") if account else None

    message = "未发现已授权 Android 真机"
    if primary:
        message = "已通过 ADB 识别 1 台真实 Android 手机"
        if primary.get("screen_awake") is False:
            message += "；手机当前锁屏/熄屏，自动操作保持停止"
    if blocked:
        message += f"；另有 {len(blocked)} 台设备因单真机试点被阻止"
    return {
        "adb": {"found": True, "path": adb, "status": "ready"},
        "devices": devices,
        "primary_device_id": primary.get("device_id") if primary else None,
        "pilot": {"limit": 1, "connected": len(connected), "blocked_extra": len(blocked)},
        "message": message,
    }


def _require_connected(device_id):
    snapshot = scan_and_sync()
    device = next((item for item in snapshot.get("devices", []) if item.get("device_id") == device_id), None)
    if not device or not device.get("connected"):
        raise ValueError("目标手机当前未通过 ADB 在线")
    return device


def screenshot_bytes(device_id):
    _require_connected(device_id)
    data = _run(["-s", device_id, "exec-out", "screencap", "-p"], timeout=12, binary=True)
    if not isinstance(data, (bytes, bytearray)) or not bytes(data).startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("ADB 截图未返回有效 PNG")
    _append_audit({"device_id": device_id, "action": "screenshot", "actor": "owner", "result": "ok"})
    return bytes(data)


def _safe_transfer_name(name):
    raw = Path(str(name or "").replace("\\", "/")).name.strip()
    if not raw or raw in {".", ".."}:
        raise ValueError("文件名不能为空")
    safe = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", raw).strip("._")
    if not safe:
        raise ValueError("文件名没有可用字符")
    return safe[:120]


def list_transfer_files(device_id):
    _require_connected(device_id)
    _shell(device_id, "mkdir", "-p", TRANSFER_DIR)
    try:
        output = _shell(device_id, "ls", "-1", TRANSFER_DIR)
    except RuntimeError:
        output = ""
    items = []
    for raw in str(output or "").splitlines():
        name = raw.strip()
        if not name or name in {".", ".."}:
            continue
        try:
            safe = _safe_transfer_name(name)
        except ValueError:
            continue
        if safe == name:
            items.append(name)
    return {"device_id": device_id, "directory": TRANSFER_DIR, "items": items[:200]}


def push_file(device_id, local_path, remote_name):
    _require_connected(device_id)
    source = Path(local_path)
    if not source.is_file():
        raise ValueError("待发送文件不存在")
    name = _safe_transfer_name(remote_name or source.name)
    _shell(device_id, "mkdir", "-p", TRANSFER_DIR)
    remote = f"{TRANSFER_DIR}/{name}"
    _run(["-s", device_id, "push", str(source), remote], timeout=60)
    event = _append_audit({
        "device_id": device_id,
        "action": "file_push",
        "actor": "owner",
        "result": "ok",
        "detail": {"name": name, "bytes": source.stat().st_size, "remote": remote},
    })
    return {"ok": True, "device_id": device_id, "name": name, "remote": remote, "event": event}


def pull_file_bytes(device_id, remote_name):
    _require_connected(device_id)
    name = _safe_transfer_name(remote_name)
    remote = f"{TRANSFER_DIR}/{name}"
    data = _run(["-s", device_id, "exec-out", "cat", remote], timeout=60, binary=True)
    if not isinstance(data, (bytes, bytearray)):
        raise RuntimeError("ADB 文件读取失败")
    _append_audit({
        "device_id": device_id,
        "action": "file_pull",
        "actor": "owner",
        "result": "ok",
        "detail": {"name": name, "bytes": len(data), "remote": remote},
    })
    return name, bytes(data)


def execute_action(payload):
    payload = payload or {}
    device_id = str(payload.get("device_id") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    actor = str(payload.get("actor") or "owner")[:40]
    if not device_id:
        raise ValueError("device_id 不能为空")
    device = _require_connected(device_id)
    runtime = _runtime_state()
    mode = (runtime.get("devices") or {}).get(device_id, {}).get("mode", "r8")
    if mode == "human" and actor != "owner":
        raise ValueError("设备处于人工接管状态")
    if device.get("screen_awake") is False and action != "power":
        _append_audit({
            "device_id": device_id,
            "action": action or "unknown",
            "actor": actor,
            "result": "blocked",
            "detail": {"reason": "screen_locked_or_off"},
        })
        raise ValueError("手机处于锁屏/熄屏状态；为避免误操作，除唤醒键外已停止设备动作")

    if action == "tap":
        x, y = int(payload.get("x")), int(payload.get("y"))
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            raise ValueError("点击坐标超出允许范围")
        _shell(device_id, "input", "tap", str(x), str(y))
        detail = {"x": x, "y": y}
    elif action == "swipe":
        x1, y1 = int(payload.get("x1")), int(payload.get("y1"))
        x2, y2 = int(payload.get("x2")), int(payload.get("y2"))
        duration = int(payload.get("duration") or 350)
        if any(v < 0 or v > 10000 for v in (x1, y1, x2, y2)) or not 50 <= duration <= 5000:
            raise ValueError("滑动参数超出允许范围")
        _shell(device_id, "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration))
        detail = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration": duration}
    elif action == "text":
        text = str(payload.get("text") or "")
        if not text or len(text) > 200:
            raise ValueError("输入文字需为 1-200 字符")
        if any(ord(ch) > 127 for ch in text):
            raise ValueError("当前 ADB 安全输入仅支持 ASCII；中文输入等待专用输入适配器")
        encoded = text.replace(" ", "%s")
        _shell(device_id, "input", "text", encoded)
        detail = {"length": len(text)}
    elif action in {"back", "home", "power"}:
        key = {"back": "4", "home": "3", "power": "26"}[action]
        _shell(device_id, "input", "keyevent", key)
        detail = {"keyevent": key}
    else:
        raise ValueError("不支持的设备动作")

    event = _append_audit({
        "device_id": device_id,
        "action": action,
        "actor": actor,
        "task_id": str(payload.get("task_id") or "")[:120] or None,
        "account_id": str(payload.get("account_id") or "")[:180] or None,
        "result": "ok",
        "detail": detail,
    })
    return {"ok": True, "device": device, "event": event}


def set_takeover(payload):
    payload = payload or {}
    device_id = str(payload.get("device_id") or "").strip()
    mode = str(payload.get("mode") or "human").strip().lower()
    if mode not in {"human", "r8"}:
        raise ValueError("mode 只能是 human 或 r8")
    _require_connected(device_id)
    state = _runtime_state()
    devices = state.setdefault("devices", {})
    previous = devices.get(device_id) or {}
    devices[device_id] = dict(previous, mode=mode, updated_at=now_iso())
    _save_runtime(state)
    event = _append_audit({
        "device_id": device_id,
        "action": "takeover" if mode == "human" else "return_to_r8",
        "actor": "owner",
        "result": "ok",
    })
    return {"ok": True, "device_id": device_id, "mode": mode, "event": event}
