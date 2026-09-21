"""Consume ChatGPT content decisions from the existing R7 bridge.

Only two dedicated kinds are accepted: ``content_production`` and ``content_qc``.
Both are validated by the content factory.  This module never executes arbitrary
commands, never introduces a second planning model and never bypasses the owner
publication approval gate.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from core.storage import now_iso
from integrations.bridge import bridge_status
from promotion import content_factory


COMMAND_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
ALLOWED_KINDS = {"content_production", "content_qc"}


def _atomic_json(path, value):
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


def _archive(root, path):
    archive = root / "archive" / path.name
    if archive.exists():
        path.unlink(missing_ok=True)
    else:
        path.replace(archive)


def _receipt(root, command_id, payload):
    value = {"command_id": command_id, "updated_at": now_iso(), **payload}
    _atomic_json(root / "outbox" / "receipts" / f"{command_id}.json", value)
    return value


def _apply_production(payload):
    plan = payload.get("production_plan")
    if not isinstance(plan, dict):
        raise ValueError("content_production必须包含production_plan对象")
    result = content_factory.apply_chatgpt_plan({
        "video_id": payload.get("video_id"),
        "campaign_id": payload.get("campaign_id") or plan.get("campaign_id"),
        "production_plan": plan,
    })
    return result, {
        "state": "accepted",
        "kind": "content_production",
        "video_id": result.get("id"),
        "campaign_id": result.get("campaign_id"),
        "plan_version": result.get("plan_version"),
        "local_state": result.get("status"),
        "note": "ChatGPT生产合同已验证并进入本地视频生产队列；发布仍需老板最终审核。",
    }


def _apply_qc(payload):
    handler = getattr(content_factory, "apply_chatgpt_qc", None)
    if not callable(handler):
        raise ValueError("当前运行时尚未启用ChatGPT成片质检扩展")
    qc = payload.get("qc") if isinstance(payload.get("qc"), dict) else payload
    result = handler({
        "video_id": payload.get("video_id") or qc.get("video_id"),
        "candidate_id": payload.get("candidate_id") or qc.get("candidate_id"),
        "decision": qc.get("decision"),
        "score": qc.get("score"),
        "reasons": qc.get("reasons") or [],
        "shot_feedback": qc.get("shot_feedback") or [],
    })
    return result, {
        "state": "accepted",
        "kind": "content_qc",
        "video_id": result.get("id"),
        "campaign_id": result.get("campaign_id"),
        "local_state": result.get("status"),
        "qc_status": (result.get("chatgpt_qc") or {}).get("status"),
        "note": "ChatGPT成片质检结果已记录；通过后进入老板最终审核，重做则自动回到ChatGPT策划。",
    }


def sync_content_plans():
    """Import all pending ChatGPT production/QC decisions before generic R7 commands."""
    status = bridge_status()
    if status.get("status") != "connected" or not status.get("bridge_root"):
        return {"synced": False, "imported": 0, "rejected": 0, "reason": status.get("message")}

    root = Path(status["bridge_root"])
    imported = 0
    rejected = 0
    imported_by_kind = {kind: 0 for kind in ALLOWED_KINDS}
    for path in sorted((root / "inbox").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        kind = str(payload.get("kind") or "").strip()
        if kind not in ALLOWED_KINDS:
            continue

        command_id = str(payload.get("id") or "").strip()
        try:
            if not COMMAND_ID.fullmatch(command_id):
                raise ValueError(f"{kind}缺少有效command_id")
            if kind == "content_production":
                _, receipt = _apply_production(payload)
            else:
                _, receipt = _apply_qc(payload)
            _receipt(root, command_id, receipt)
            imported += 1
            imported_by_kind[kind] += 1
        except (OSError, ValueError, TypeError) as error:
            safe_id = command_id if COMMAND_ID.fullmatch(command_id) else f"invalid-content-{path.stem[:40]}"
            _receipt(root, safe_id, {
                "state": "rejected",
                "kind": kind,
                "error": str(error)[:500],
                "note": "内容指令未通过安全/结构校验，未进入本地执行或审核状态。",
            })
            rejected += 1
        finally:
            try:
                _archive(root, path)
            except OSError:
                pass
    return {
        "synced": True,
        "imported": imported,
        "rejected": rejected,
        "imported_by_kind": imported_by_kind,
    }
