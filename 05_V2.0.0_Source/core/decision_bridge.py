"""Export the latest R7 manager report for the ChatGPT strategy layer."""

import json
import os
import tempfile
from pathlib import Path

from core.storage import now_iso


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


def export_decision_handoff(report):
    """Write the latest R7 decision context plus pending R8 content requests."""
    from integrations.bridge import bridge_status
    from promotion.content_factory import pending_chatgpt_handoff

    status = bridge_status()
    if status.get("status") != "connected" or not status.get("bridge_root"):
        return {"exported": False, "status": status.get("status"), "reason": status.get("message")}
    root = Path(status["bridge_root"])
    content_requests = pending_chatgpt_handoff()
    payload = {
        "schema": "kazuizhi-chatgpt-strategy-handoff/v2",
        "exported_at": now_iso(),
        "source": "R7 autonomous decision center + R8 content factory",
        "decision_center": report,
        "content_production_requests": content_requests,
        "instruction": (
            "ChatGPT是唯一总控制：基于真实员工汇报、经理判断和待生产内容请求，负责经营判断、选题、痛点、"
            "标题、文案、深层脚本、分镜、素材决策、平台适配和质检决策。对content_production_requests中的"
            "任务，按kazuizhi-content-production/v1生成结构化production_plan，并以kind=content_production"
            "写回bridge inbox。R8/RTX3060/本地程序只负责执行。资金事项不得自动执行。"
        ),
    }
    target = root / "outbox" / "latest_decision.json"
    _atomic_json(target, payload)
    return {
        "exported": True,
        "path": str(target),
        "exported_at": payload["exported_at"],
        "content_requests": content_requests.get("count", 0),
    }
