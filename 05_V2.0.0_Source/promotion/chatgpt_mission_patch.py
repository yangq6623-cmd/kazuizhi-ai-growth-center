"""Extend the existing ChatGPT bridge with validated Mission decisions."""
from __future__ import annotations

import json
from pathlib import Path

from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
from integrations.bridge import bridge_status
from promotion import chatgpt_orchestrator as orchestrator

_INSTALLED = False
_ORIGINAL_SYNC = None


def _sync_mission_decisions():
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
        if str(payload.get("kind") or "").strip() != "mission_decision":
            continue
        command_id = str(payload.get("id") or "").strip()
        try:
            if not orchestrator.COMMAND_ID.fullmatch(command_id):
                raise ValueError("mission_decision缺少有效command_id")
            result = apply_chatgpt_mission_decision(payload)
            orchestrator._receipt(root, command_id, {
                "state": "accepted",
                "kind": "mission_decision",
                "action": result.get("action"),
                "mission_id": result.get("mission_id"),
                "growth_id": result.get("growth_id"),
                "video_id": result.get("video_id"),
                "note": "ChatGPT Mission 决策已通过非资金自治边界并进入共享R7/R8流水线。",
            })
            imported += 1
        except (OSError, ValueError, TypeError) as error:
            safe_id = command_id if orchestrator.COMMAND_ID.fullmatch(command_id) else f"invalid-mission-{path.stem[:40]}"
            orchestrator._receipt(root, safe_id, {
                "state": "rejected",
                "kind": "mission_decision",
                "error": str(error)[:500],
                "note": "Mission决策未通过结构/真实性/权限边界校验，未执行。",
            })
            rejected += 1
        finally:
            try:
                orchestrator._archive(root, path)
            except OSError:
                pass
    return {"synced": True, "imported": imported, "rejected": rejected}


def sync_content_plans():
    mission = _sync_mission_decisions()
    content = _ORIGINAL_SYNC()
    imported_by_kind = dict(content.get("imported_by_kind") or {})
    imported_by_kind["mission_decision"] = int(mission.get("imported") or 0)
    return {
        **content,
        "imported": int(content.get("imported") or 0) + int(mission.get("imported") or 0),
        "rejected": int(content.get("rejected") or 0) + int(mission.get("rejected") or 0),
        "imported_by_kind": imported_by_kind,
        "mission_decisions": mission,
    }


def install():
    global _INSTALLED, _ORIGINAL_SYNC
    if _INSTALLED:
        return
    _ORIGINAL_SYNC = orchestrator.sync_content_plans
    orchestrator.sync_content_plans = sync_content_plans
    _INSTALLED = True


install()

# R8-22 through R8-23.5 are cumulative production patches. The desktop
# entrypoint historically stopped importing at R8-20, which allowed a newer
# package to paint the recovery shell while silently falling back to older
# runtime/API behavior. Load the later patches here because this module is the
# final side-effect patch imported by run.py before the server is created.
# Import order is intentional: convergence -> growth OS -> runtime truth/safety
# -> candidate -> route recovery -> cumulative regression recovery.
from backend import r8_22_autonomy_convergence_patch as _r8_22_autonomy_convergence_patch  # noqa: F401,E402
from backend import r8_23_growth_os_patch as _r8_23_growth_os_patch  # noqa: F401,E402
from backend import r8_23_2_runtime_truth_patch as _r8_23_2_runtime_truth_patch  # noqa: F401,E402
from backend import r8_23_2_runtime_safety_patch as _r8_23_2_runtime_safety_patch  # noqa: F401,E402
from backend import r8_23_3_candidate_patch as _r8_23_3_candidate_patch  # noqa: F401,E402
from backend import r8_23_4_runtime_route_recovery_patch as _r8_23_4_runtime_route_recovery_patch  # noqa: F401,E402
from backend import r8_23_5_full_recovery_patch as _r8_23_5_full_recovery_patch  # noqa: F401,E402
