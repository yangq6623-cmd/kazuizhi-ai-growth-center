"""Truthful retry/watchdog layer for R8 ChatGPT content handoffs.

A writable sync folder is not the same thing as ChatGPT receiving a request.
This module records only states the local runtime can prove: bridge unavailable,
request exported, waiting for a returned production/QC decision, returned, or
retry exhausted. It never fabricates an acknowledgement from ChatGPT.
"""

from __future__ import annotations

from datetime import datetime

from core.decision_bridge import export_decision_handoff
from core.decision_center import decision_snapshot
from core.storage import now_iso
from integrations.bridge import bridge_status
from promotion import content_factory as cf

RETRY_AFTER_SECONDS = 300
MAX_RETRIES = 3
PENDING_STATES = {"等待ChatGPT策划", "退回重做", "等待ChatGPT质检"}


def _parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _age_seconds(value, now):
    parsed = _parse(value)
    if parsed is None:
        return None
    try:
        return max(0, int((now - parsed).total_seconds()))
    except TypeError:
        return None


def _phase_for(video):
    if video.get("plan_received_at") or video.get("production_plan"):
        return "production_contract_received"
    qc = video.get("chatgpt_qc") if isinstance(video.get("chatgpt_qc"), dict) else {}
    if qc.get("status") in {"passed", "rework"}:
        return "qc_returned"
    if video.get("status") == "等待ChatGPT质检":
        return "waiting_qc_return"
    if video.get("status") in {"等待ChatGPT策划", "退回重做"}:
        return "waiting_plan_return"
    return "local_execution"


def _mark_nonpending_truth(data):
    changed = False
    for video in data.get("videos", []):
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else None
        if handoff is None:
            continue
        # A retry-exhausted exception remains truthful until a real plan/QC
        # response changes the task state. Do not silently turn it back into a
        # generic local-execution state on the next scheduler tick.
        if video.get("status") == "异常待处理" and handoff.get("phase") == "retry_exhausted":
            continue
        phase = _phase_for(video)
        if video.get("status") not in PENDING_STATES and phase != handoff.get("phase"):
            handoff["phase"] = phase
            handoff["response_at"] = video.get("plan_received_at") or (video.get("chatgpt_qc") or {}).get("reviewed_at") or now_iso()
            handoff["updated_at"] = now_iso()
            changed = True
    return changed


def sync_chatgpt_handoffs(force=False):
    """Export pending ChatGPT requests, retry with bounds, and expose truthful state.

    The first export is immediate. A request is re-exported at most three times,
    spaced by RETRY_AFTER_SECONDS. After the final retry window expires the task
    becomes an explicit human-visible exception instead of waiting forever.
    A later valid ChatGPT response is still accepted by the normal orchestrator
    and will recover the task automatically.
    """
    data = cf._load()
    now = datetime.now().astimezone()
    changed = _mark_nonpending_truth(data)
    pending = [video for video in data.get("videos", []) if video.get("status") in PENDING_STATES]
    if not pending:
        if changed:
            cf._save(data)
        return {"pending": 0, "exported": False, "reason": "no_pending_chatgpt_handoff"}

    bridge = bridge_status()
    connected = bridge.get("status") == "connected" and bool(bridge.get("bridge_root"))
    due = []

    for video in pending:
        handoff = video.setdefault("chatgpt_handoff", {})
        handoff.setdefault("kind", "content_qc" if video.get("status") == "等待ChatGPT质检" else "content_production")
        handoff.setdefault("retry_count", 0)
        handoff.setdefault("max_retries", MAX_RETRIES)
        handoff["updated_at"] = now_iso()

        if not connected:
            handoff["phase"] = "bridge_unavailable"
            handoff["bridge_status"] = bridge.get("status") or "not_connected"
            handoff["message"] = "双向同步桥未连接；请求尚未证明已发送给ChatGPT。"
            video["bottleneck"] = "ChatGPT同步桥未连接，生产请求尚未发送"
            video["auto_action"] = "系统持续检查同步桥；恢复后自动发送，无需重复创建任务"
            changed = True
            continue

        last_sent = handoff.get("last_exported_at")
        age = _age_seconds(last_sent, now)
        retries = int(handoff.get("retry_count") or 0)

        if not last_sent or force:
            due.append((video, handoff, False))
        elif age is not None and age >= RETRY_AFTER_SECONDS and retries < MAX_RETRIES:
            due.append((video, handoff, True))
        elif age is not None and age >= RETRY_AFTER_SECONDS and retries >= MAX_RETRIES:
            handoff["phase"] = "retry_exhausted"
            handoff["message"] = f"已自动重发 {MAX_RETRIES} 次仍未收到结构化返回。"
            handoff["exhausted_at"] = now_iso()
            video["status"] = "异常待处理"
            video["retry_count"] = max(int(video.get("retry_count") or 0), MAX_RETRIES)
            video["bottleneck"] = "ChatGPT生产/QC请求连续重发仍未返回"
            video["auto_action"] = "已停止无限等待；请检查ChatGPT侧桥接/自动化是否在线，恢复后可自动继续"
            changed = True
        else:
            handoff["phase"] = "waiting_response"
            handoff["bridge_status"] = "connected"
            handoff["message"] = "请求已写入同步桥；正在等待ChatGPT返回结构化结果。"
            changed = True

    if changed:
        cf._save(data)

    exported = None
    if due and connected:
        exported = export_decision_handoff(decision_snapshot())
        if exported.get("exported"):
            data = cf._load()
            due_ids = {item[0].get("id"): item[2] for item in due}
            for video in data.get("videos", []):
                if video.get("id") not in due_ids or video.get("status") not in PENDING_STATES:
                    continue
                handoff = video.setdefault("chatgpt_handoff", {})
                is_retry = due_ids[video.get("id")]
                if not handoff.get("first_exported_at"):
                    handoff["first_exported_at"] = now_iso()
                if is_retry:
                    handoff["retry_count"] = min(MAX_RETRIES, int(handoff.get("retry_count") or 0) + 1)
                handoff["last_exported_at"] = now_iso()
                handoff["phase"] = "waiting_response"
                handoff["bridge_status"] = "connected"
                handoff["message"] = "请求已写入同步桥；等待ChatGPT返回结构化结果。"
                video["bottleneck"] = "等待ChatGPT返回结构化生产/QC结果"
                video["auto_action"] = (
                    f"已写入同步桥；若 {RETRY_AFTER_SECONDS // 60} 分钟无返回将自动重发，"
                    f"最多 {MAX_RETRIES} 次"
                )
            cf._save(data)

    return {
        "pending": len(pending),
        "bridge_status": bridge.get("status"),
        "due": len(due),
        "exported": bool(exported and exported.get("exported")),
        "retry_after_seconds": RETRY_AFTER_SECONDS,
        "max_retries": MAX_RETRIES,
        "handoff": exported,
    }
