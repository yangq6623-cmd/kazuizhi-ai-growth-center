"""Consume ChatGPT content-production plans from the existing R7 bridge.

This is intentionally narrow: it accepts only ``kind=content_production`` JSON,
validates it through the production contract, stores the plan, and returns an
auditable receipt.  It never executes arbitrary commands or bypasses owner
publication approval.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from core.storage import now_iso
from integrations.bridge import bridge_status
from promotion.content_factory import apply_chatgpt_plan


COMMAND_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")


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


def sync_content_plans():
    """Import all pending ChatGPT production contracts without touching R7 commands."""
    status = bridge_status()
    if status.get("status") != "connected" or not status.get("bridge_root"):
        return {"synced": False, "imported": 0, "rejected": 0, "reason": status.get("message")}

    root = Path(status["bridge_root"])
    imported = 0
    rejected = 0
    for path in sorted((root / "inbox").glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if str(payload.get("kind") or "").strip() != "content_production":
            continue

        command_id = str(payload.get("id") or "").strip()
        try:
            if not COMMAND_ID.fullmatch(command_id):
                raise ValueError("content_production缺少有效command_id")
            plan = payload.get("production_plan")
            if not isinstance(plan, dict):
                raise ValueError("content_production必须包含production_plan对象")
            result = apply_chatgpt_plan({
                "video_id": payload.get("video_id"),
                "campaign_id": payload.get("campaign_id") or plan.get("campaign_id"),
                "production_plan": plan,
            })
            _receipt(root, command_id, {
                "state": "accepted",
                "video_id": result.get("id"),
                "campaign_id": result.get("campaign_id"),
                "plan_version": result.get("plan_version"),
                "local_state": result.get("status"),
                "note": "ChatGPT生产合同已验证并进入本地视频生产队列；发布仍需老板最终审核。",
            })
            imported += 1
        except (OSError, ValueError, TypeError) as error:
            safe_id = command_id if COMMAND_ID.fullmatch(command_id) else f"invalid-content-{path.stem[:40]}"
            _receipt(root, safe_id, {
                "state": "rejected",
                "error": str(error)[:500],
                "note": "生产合同未通过安全/结构校验，未进入本地执行队列。",
            })
            rejected += 1
        finally:
            try:
                _archive(root, path)
            except OSError:
                pass
    return {"synced": True, "imported": imported, "rejected": rejected}
