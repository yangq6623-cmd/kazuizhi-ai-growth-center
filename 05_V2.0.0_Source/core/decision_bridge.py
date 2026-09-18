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
    """Write one latest-decision handoff only when the existing bridge is healthy."""
    from integrations.bridge import bridge_status

    status = bridge_status()
    if status.get("status") != "connected" or not status.get("bridge_root"):
        return {"exported": False, "status": status.get("status"), "reason": status.get("message")}
    root = Path(status["bridge_root"])
    payload = {
        "schema": "kazuizhi-chatgpt-strategy-handoff/v1",
        "exported_at": now_iso(),
        "source": "R7 autonomous decision center",
        "decision_center": report,
        "instruction": "请由 ChatGPT 总控制大脑基于真实员工汇报和经理判断做跨部门复盘；非资金低风险策略可回传 R7，资金事项不得自动执行。",
    }
    target = root / "outbox" / "latest_decision.json"
    _atomic_json(target, payload)
    return {"exported": True, "path": str(target), "exported_at": payload["exported_at"]}
