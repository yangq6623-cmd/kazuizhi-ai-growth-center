"""Auditable bidirectional bridge between the local R7 runtime and a synced folder.

The bridge never requires a cloud vendor in core code. Point it at any local
folder that is synchronised by Google Drive, OneDrive or another approved
transport. R7 keeps running locally when the folder is unavailable.
"""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from core.storage import now_iso, read_json, write_json


CONFIG_PATH = "integrations/bridge.json"
STATE_PATH = "bridge/state.json"
COMMANDS_PATH = "bridge/commands.json"
BRIDGE_DIR = "Kazuizhi_AI_Bridge"
ALLOWED_KINDS = {"manual_task", "daily_review", "diagnostics"}
COMMAND_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


def _drive_relative_tail(value):
    """Return the Windows path after ``X:\`` for drive-letter recovery."""
    text = str(value or "").strip().replace("\\", "/")
    match = re.match(r"^[A-Za-z]:/(.+)$", text)
    return match.group(1).strip("/") if match else ""


def _config():
    env_root = os.environ.get("KAZUIZHI_BRIDGE_ROOT", "").strip()
    saved = read_json(CONFIG_PATH, {"provider": "filesystem_sync", "root": "", "enabled": False})
    if env_root:
        saved = dict(saved, root=env_root, enabled=True, source="environment")
    return saved


def _root(config=None):
    config = config or _config()
    value = str(config.get("root") or "").strip()
    if not value:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path if path.name == BRIDGE_DIR else path / BRIDGE_DIR


def _layout(root):
    for relative in ("inbox", "archive", "outbox", "outbox/reports", "outbox/receipts"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def _probe_root(root):
    """Verify bridge read/write access without fixed-name probe races.

    Several UI endpoints can call bridge_status concurrently. A shared probe
    filename let one request delete another request's probe, briefly reporting
    Google Drive as unavailable. Use a unique tempfile and make cleanup
    best-effort so cloud sync latency cannot flip a healthy bridge to degraded.
    """
    probe = None
    try:
        _layout(root)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root,
            prefix=".bridge-probe.", suffix=".tmp", delete=False,
        ) as handle:
            probe = Path(handle.name)
            handle.write("ok")
            handle.flush()
            os.fsync(handle.fileno())
        if probe.read_text(encoding="utf-8") != "ok":
            raise OSError("bridge probe mismatch")
        return True, None
    except OSError as exc:
        return False, str(exc)[:240]
    finally:
        if probe is not None and probe.exists():
            try:
                probe.unlink()
            except OSError:
                pass


def _candidate_relocated_roots(saved_root):
    """Yield mounted Windows drives containing the same saved relative folder.

    Google Drive can silently move from e.g. G: to D:.  The persisted bridge
    configuration remains the source of truth; only the drive letter may be
    repaired.  We never scan arbitrary folders or clear the old configuration.
    """
    if os.name != "nt":
        return []
    tail = _drive_relative_tail(saved_root)
    if not tail:
        return []
    original = str(saved_root).replace("\\", "/").lower()
    results = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
        drive = Path(f"{letter}:/")
        try:
            if not drive.exists():
                continue
            candidate = drive / Path(tail)
            if str(candidate).replace("\\", "/").lower() == original:
                continue
            # Never create an AI_Command folder just because another drive exists.
            # Auto-recovery is allowed only when the exact saved relative folder
            # already exists on that mounted drive.
            if candidate.is_dir():
                results.append(candidate)
        except OSError:
            continue
    return results


def _recover_moved_root(config):
    """Repair only the drive letter of an already-saved bridge root."""
    saved_root = str(config.get("root") or "").strip()
    if not saved_root or config.get("source") == "environment":
        return config, None
    for candidate in _candidate_relocated_roots(saved_root):
        bridge_root = candidate if candidate.name == BRIDGE_DIR else candidate / BRIDGE_DIR
        connected, _ = _probe_root(bridge_root)
        if not connected:
            continue
        updated = dict(config)
        updated.update(
            root=str(candidate),
            enabled=True,
            source="auto_drive_recovery",
            recovered_from=saved_root,
            recovered_at=now_iso(),
            drive_relative_tail=_drive_relative_tail(str(candidate)),
        )
        write_json(CONFIG_PATH, updated)
        return updated, saved_root
    return config, None


def _write_external(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
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


def configure_bridge(payload):
    root_text = str(payload.get("root") or "").strip()
    if not root_text:
        raise ValueError("请填写双向桥本地同步目录")
    base = Path(os.path.expandvars(os.path.expanduser(root_text)))
    if not base.is_absolute():
        raise ValueError("双向桥目录必须使用绝对路径")
    root = base if base.name == BRIDGE_DIR else base / BRIDGE_DIR
    connected, error = _probe_root(root)
    if not connected:
        raise ValueError("双向桥目录不可写，请检查云盘同步目录或权限")
    config = {
        "provider": "filesystem_sync",
        "root": str(base),
        "enabled": True,
        "configured_at": now_iso(),
        "source": "owner_config",
        "drive_relative_tail": _drive_relative_tail(str(base)),
    }
    write_json(CONFIG_PATH, config)
    return bridge_status()


def disable_bridge():
    config = _config()
    config.update(enabled=False, disabled_at=now_iso())
    write_json(CONFIG_PATH, config)
    return bridge_status()


def _pending_count(root):
    commands = read_json(COMMANDS_PATH, {"items": {}}).get("items", {})
    count = 0
    for path in (root / "inbox").glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            command_id = str(payload.get("id") or "")
        except (OSError, ValueError, TypeError):
            command_id = ""
        if command_id not in commands:
            count += 1
    return count


def bridge_status():
    config = _config()
    root = _root(config)
    state = read_json(STATE_PATH, {})
    if not config.get("enabled") or root is None:
        return {
            "id": "operations_bridge", "name": "双向运营桥", "status": "not_connected",
            "status_label": "未配置", "provider": config.get("provider", "filesystem_sync"),
            "root": str(config.get("root") or ""), "bridge_root": None,
            "operating_mode": "local_autonomous", "operating_mode_label": "本地自主运行",
            "message": "未配置云端同步目录；R7 会继续执行已批准的本地任务。",
            "last_sync_at": state.get("last_sync_at"), "last_report_at": state.get("last_report_at"),
            "last_error": state.get("last_error"), "pending_commands": 0,
            "offline_policy": "ChatGPT/云端不可用时继续执行最后已批准的本地低风险任务，并积累结果等待下次同步。",
        }
    connected, error = _probe_root(root)
    recovered_from = None
    if not connected:
        config, recovered_from = _recover_moved_root(config)
        if recovered_from:
            root = _root(config)
            connected, error = _probe_root(root)
    message = "双向桥可用；本机上报、AI计划接收和执行回执将自动同步。" if connected else \
              "同步目录暂不可用；R7 已自动退回本地自主运行。"
    if connected and recovered_from:
        message = f"检测到云盘盘符变化，已从 {recovered_from} 自动恢复到 {config.get('root')}；双向同步已恢复。"
    return {
        "id": "operations_bridge", "name": "双向运营桥",
        "status": "connected" if connected else "degraded",
        "status_label": "已连接" if connected else "同步目录不可用",
        "provider": config.get("provider", "filesystem_sync"), "root": str(config.get("root") or ""),
        "bridge_root": str(root),
        "recovered_from": recovered_from or config.get("recovered_from"),
        "operating_mode": "bridge_plus_local" if connected else "local_autonomous",
        "operating_mode_label": "AI双向运营" if connected else "本地自主运行",
        "message": message,
        "last_sync_at": state.get("last_sync_at"), "last_report_at": state.get("last_report_at"),
        "last_error": error or state.get("last_error"),
        "pending_commands": _pending_count(root) if connected else 0,
        "offline_policy": "ChatGPT/云端不可用时继续执行最后已批准的本地低风险任务，并积累结果等待下次同步。",
    }


def build_report():
    from ai_center.daily_review import latest_plan, latest_review
    from analytics.business_metrics import build_analytics
    from analytics.operation_summary import build_summary
    from core.r7_engine import audit_history, engine_status, list_jobs
    from memory.memory_store import get_memory
    from operations.workspace import command_center
    from promotion.content_center import history as promotion_history

    jobs = list_jobs()
    audit = audit_history()
    memory = get_memory()
    analytics = build_analytics()
    dashboard = command_center()
    return {
        "schema": "kazuizhi-operations-bridge/v1",
        "generated_at": now_iso(),
        "runtime": {"release": "R7", "mode": "local_autonomous_with_bridge"},
        "task_engine": engine_status(),
        "jobs": {"count": jobs.get("count", 0), "recent": jobs.get("items", [])[:20]},
        "dashboard": dashboard,
        "daily_summary": build_summary(),
        "daily_review": latest_review(),
        "tomorrow_plan": latest_plan(),
        "content": {"recent": promotion_history().get("items", [])[:10]},
        "memory": {"count": len(memory.get("entries", [])), "updated_at": memory.get("updated_at")},
        "business_data": {"status": analytics.get("status"), "source": analytics.get("source"),
                          "as_of": analytics.get("as_of")},
        "audit": {"integrity": audit.get("integrity"), "recent": audit.get("events", [])[-20:]},
        "truth_policy": "未接入的曝光、咨询、订单、收入等经营指标保持未接入；不得用推测数字替代。",
    }


def export_report():
    status = bridge_status()
    if status["status"] != "connected":
        return {"exported": False, "status": status}
    root = Path(status["bridge_root"])
    report = build_report()
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    _write_external(root / "outbox" / "latest_status.json", report)
    _write_external(root / "outbox" / "reports" / f"report_{stamp}.json", report)
    state = read_json(STATE_PATH, {})
    state.update(last_report_at=now_iso(), last_error=None)
    write_json(STATE_PATH, state)
    return {"exported": True, "report": report, "path": str(root / "outbox" / "latest_status.json")}


def _receipt(root, command_id, value):
    payload = {"command_id": command_id, "updated_at": now_iso(), **value}
    _write_external(root / "outbox" / "receipts" / f"{command_id}.json", payload)
    return payload


def _archive(root, path):
    try:
        archived = root / "archive" / path.name
        if not archived.exists():
            path.replace(archived)
        else:
            path.unlink()
    except OSError:
        pass


def _refresh_receipts(root, records):
    from core.r7_engine import list_jobs
    jobs = {item["id"]: item for item in list_jobs().get("items", [])}
    for command_id, record in records.items():
        job = jobs.get(record.get("job_id"))
        if not job:
            continue
        _receipt(root, command_id, {
            "accepted_at": record.get("accepted_at"), "job_id": job["id"],
            "state": job.get("state"), "progress": job.get("progress"),
            "result": job.get("result"), "error": job.get("error"),
            "note": "云端计划已转换为本地任务；任务仍受本机审批、审计和安全策略约束。",
        })


def sync_once():
    status = bridge_status()
    if status["status"] != "connected":
        state = read_json(STATE_PATH, {})
        state.update(last_error=status.get("last_error") or status.get("message"))
        write_json(STATE_PATH, state)
        return {"synced": False, "imported": 0, "status": status}
    root = Path(status["bridge_root"])
    exported = export_report()
    store = read_json(COMMANDS_PATH, {"items": {}})
    records = store.setdefault("items", {})
    imported = 0
    rejected = 0
    for path in sorted((root / "inbox").glob("*.json")):
        command_id = ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            command_id = str(payload.get("id") or "").strip()
            if not COMMAND_ID.fullmatch(command_id):
                raise ValueError("AI 指令缺少有效 command_id")
            if command_id in records:
                _archive(root, path)
                continue
            kind = str(payload.get("kind") or "manual_task")
            if kind not in ALLOWED_KINDS:
                raise ValueError("该 AI 指令类型不在 R7 安全白名单")
            title = str(payload.get("title") or "").strip()
            if not title or len(title) > 160:
                raise ValueError("AI 指令任务名称需为 1 到 160 字")
            due_at = str(payload.get("due_at") or "").strip()
            from core.r7_engine import create_job
            job = create_job({"kind": kind, "title": title, "due_at": due_at})
            records[command_id] = {"job_id": job["id"], "accepted_at": now_iso(),
                                   "source_file": path.name, "kind": kind, "title": title}
            _receipt(root, command_id, {
                "accepted_at": records[command_id]["accepted_at"], "job_id": job["id"],
                "state": job["state"], "progress": job["progress"],
                "note": "指令已接收并转换为待本机审批任务；云端不能绕过本机安全策略。",
            })
            imported += 1
        except (OSError, ValueError, TypeError) as exc:
            if not COMMAND_ID.fullmatch(command_id):
                command_id = "invalid-" + path.stem[:50]
            if command_id not in records:
                records[command_id] = {"job_id": None, "accepted_at": now_iso(),
                                       "source_file": path.name, "error": str(exc)[:300]}
                _receipt(root, command_id, {"state": "rejected", "error": str(exc)[:300]})
                rejected += 1
        _archive(root, path)
    write_json(COMMANDS_PATH, store)
    _refresh_receipts(root, records)
    state = read_json(STATE_PATH, {})
    state.update(last_sync_at=now_iso(), last_error=None, imported_total=len([x for x in records.values() if x.get("job_id")]),
                 rejected_total=len([x for x in records.values() if x.get("error")]))
    write_json(STATE_PATH, state)
    latest = export_report()
    return {"synced": True, "imported": imported, "rejected": rejected,
            "status": bridge_status(), "report": latest.get("report") or exported.get("report")}


def self_test():
    """Exercise the real bridge path without bypassing local approval policy."""
    status = bridge_status()
    checks = []

    def mark(name, passed, message):
        checks.append({"name": name, "passed": bool(passed), "message": str(message)})
        return bool(passed)

    if status.get("status") != "connected" or not status.get("bridge_root"):
        mark("根目录", False, status.get("message") or "双向桥未连接")
        return {"passed": False, "command_id": None, "job_id": None, "checks": checks,
                "message": "双向桥闭环测试失败：请先连接可写的同步根目录。"}

    root = Path(status["bridge_root"])
    root_ok, root_error = _probe_root(root)
    mark("根目录", root_ok, str(root) if root_ok else (root_error or "根目录不可写"))
    if not root_ok:
        return {"passed": False, "command_id": None, "job_id": None, "checks": checks,
                "message": "双向桥闭环测试失败：根目录不可写。"}

    stamp = datetime.now().astimezone().strftime("%Y%m%d%H%M%S%f")
    command_id = f"selftest-{stamp}"
    filename = f"{command_id}.json"
    inbox_path = root / "inbox" / filename
    archive_path = root / "archive" / filename
    receipt_path = root / "outbox" / "receipts" / f"{command_id}.json"
    payload = {
        "id": command_id,
        "kind": "manual_task",
        "title": "双向桥一键闭环自检：验证指令接收、任务创建、归档和回执",
        "due_at": "",
    }

    try:
        _write_external(inbox_path, payload)
        parsed = json.loads(inbox_path.read_text(encoding="utf-8"))
        mark("inbox 写入", parsed.get("id") == command_id, str(inbox_path))
        mark("指令解析", parsed.get("kind") in ALLOWED_KINDS and bool(parsed.get("title")),
             "JSON 格式与安全白名单校验通过")
    except (OSError, ValueError, TypeError) as exc:
        mark("inbox 写入", False, str(exc)[:240])
        return {"passed": False, "command_id": command_id, "job_id": None, "checks": checks,
                "message": "双向桥闭环测试失败：无法写入或解析测试指令。"}

    sync_result = sync_once()
    records = read_json(COMMANDS_PATH, {"items": {}}).get("items", {})
    record = records.get(command_id) or {}
    job_id = record.get("job_id")
    mark("任务创建", bool(job_id) and sync_result.get("imported", 0) >= 1,
         f"job_id={job_id or '未创建'}")
    mark("archive", archive_path.exists(), str(archive_path))

    receipt = {}
    try:
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_ok = receipt.get("command_id") == command_id and receipt.get("job_id") == job_id
        mark("receipt", receipt_ok,
             f"state={receipt.get('state') or '缺失'}; path={receipt_path}")
    except (OSError, ValueError, TypeError) as exc:
        mark("receipt", False, str(exc)[:240])

    passed = all(item["passed"] for item in checks)
    return {
        "passed": passed,
        "command_id": command_id,
        "job_id": job_id,
        "checks": checks,
        "receipt": receipt,
        "message": "双向桥闭环测试通过；测试任务仍遵守本机审批策略。" if passed else
                   "双向桥闭环测试未完全通过，请按失败项检查。",
    }


def list_bridge_commands():
    data = read_json(COMMANDS_PATH, {"items": {}}).get("items", {})
    items = [{"command_id": key, **value} for key, value in data.items()]
    items.sort(key=lambda item: item.get("accepted_at") or "", reverse=True)
    return {"items": items[:100], "count": len(items)}