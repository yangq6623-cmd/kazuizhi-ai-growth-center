"""Truthful retry/watchdog layer for R8 content handoffs.

Normal ChatGPT is the strategic owner brain.  A validated ChatGPT Mission may
continue routine non-financial content planning locally without requiring a
permanently-open chat window or an OpenAI API key.  Tasks that are not covered
by that Mission authorization still use the bounded ChatGPT handoff path below.
No state here fabricates a ChatGPT acknowledgement or an external promotion
result.
"""

from __future__ import annotations

from datetime import datetime

from core.decision_bridge import export_decision_handoff
from core.decision_center import decision_snapshot
from core.storage import now_iso
from integrations.bridge import bridge_status
from integrations.chatgpt_control import (
    CONNECTED_VERIFIED,
    DEGRADED,
    HUMAN_ACTION_REQUIRED,
    WAITING_RESPONSE,
    control_status,
    set_runtime_state,
)
from promotion import content_factory as cf

RETRY_AFTER_SECONDS = 300
MAX_RETRIES = 3
PENDING_STATES = {"等待ChatGPT策划", "退回重做", "等待ChatGPT质检"}
CONTROL_ISSUE_PREFIX = "[content-handoff] "
MISSION_SOURCE = "ChatGPT自治经营决策"


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


def _set_control_truth(state_name, message):
    """Update the canonical control state only after real connector proof exists."""
    try:
        current = control_status()
        if not current.get("verified"):
            return current
        return set_runtime_state(state_name, issue=f"{CONTROL_ISSUE_PREFIX}{message}" if message else None)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _clear_own_control_issue_if_resolved():
    try:
        current = control_status()
        issue = str(current.get("runtime_issue") or "")
        if current.get("verified") and issue.startswith(CONTROL_ISSUE_PREFIX) and current.get("connection_state") in {
            WAITING_RESPONSE, DEGRADED, HUMAN_ACTION_REQUIRED,
        }:
            return set_runtime_state(CONNECTED_VERIFIED, issue=None)
    except (OSError, RuntimeError, TypeError, ValueError):
        return None
    return None


def _mark_nonpending_truth(data):
    changed = False
    for video in data.get("videos", []):
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else None
        if handoff is None:
            continue
        if video.get("status") == "异常待处理" and handoff.get("phase") == "retry_exhausted":
            continue
        phase = _phase_for(video)
        if video.get("status") not in PENDING_STATES and phase != handoff.get("phase"):
            handoff["phase"] = phase
            handoff["response_at"] = video.get("plan_received_at") or (video.get("chatgpt_qc") or {}).get("reviewed_at") or now_iso()
            handoff["updated_at"] = now_iso()
            changed = True
    return changed


def _recover_authorized_local_plans():
    """Recover routine production when ChatGPT already approved the parent Mission.

    This does not apply to post-render QC or arbitrary locally-created campaigns.
    It only converts content-production tasks whose campaign source proves that a
    validated ChatGPT Decision Pack created the Mission.
    """
    data = cf._load()
    campaign_by_id = {x.get("id"): x for x in data.get("campaigns", []) if isinstance(x, dict)}
    candidate_ids = []
    for video in data.get("videos", []):
        if video.get("production_plan"):
            continue
        if video.get("status") not in {"等待ChatGPT策划", "退回重做", "异常待处理"}:
            continue
        campaign = campaign_by_id.get(video.get("campaign_id"))
        if str((campaign or {}).get("source_type") or "").strip() != MISSION_SOURCE:
            continue
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        if video.get("status") == "异常待处理" and handoff.get("kind") not in {None, "content_production"}:
            continue
        candidate_ids.append(video.get("id"))

    if not candidate_ids:
        return []

    from promotion.local_mission_planner import recover_video

    recovered = []
    for video_id in candidate_ids:
        try:
            result = recover_video(video_id)
            if result:
                recovered.append(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            recovered.append({"video_id": video_id, "status": "failed", "error": str(error)[:300]})
    return recovered


def sync_chatgpt_handoffs(force=False):
    """Keep content work moving while preserving truthful ChatGPT boundaries.

    First, a routine production request may be recovered locally when its parent
    Mission was already created by a validated ChatGPT Decision Pack.  Remaining
    requests use the legacy bounded handoff path: immediate export, at most three
    retries, then a visible exception instead of infinite waiting.
    """
    local_recovered = _recover_authorized_local_plans()
    data = cf._load()
    now = datetime.now().astimezone()
    changed = _mark_nonpending_truth(data)
    pending = [video for video in data.get("videos", []) if video.get("status") in PENDING_STATES]
    if not pending:
        if changed:
            cf._save(data)
        _clear_own_control_issue_if_resolved()
        return {
            "pending": 0,
            "exported": False,
            "reason": "no_pending_chatgpt_handoff",
            "local_recovered": local_recovered,
        }

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
            handoff["message"] = "备用同步桥未连接；请求尚未证明已发送给 ChatGPT。"
            video["bottleneck"] = "ChatGPT 内容交接传输不可用，生产请求尚未证明送达"
            video["auto_action"] = "系统持续检查传输通道；恢复后自动发送。备用文件桥在线状态不等于 ChatGPT 已连接。"
            _set_control_truth(DEGRADED, "内容生产/QC 传输通道不可用；本地已批准任务继续运行，新的 ChatGPT 交接暂缓。")
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
            video["auto_action"] = "已停止无限等待；请检查 ChatGPT 总控连接/传输适配器。恢复后可自动继续；未通过 QC 的成片不会自动发布。"
            _set_control_truth(HUMAN_ACTION_REQUIRED, f"内容生产/QC 已重试 {MAX_RETRIES} 次仍无返回，已停止无限等待。")
            changed = True
        else:
            handoff["phase"] = "waiting_response"
            handoff["bridge_status"] = "connected"
            handoff["message"] = "请求已写入备用传输通道；正在等待 ChatGPT 返回结构化结果。"
            _set_control_truth(WAITING_RESPONSE, "内容生产/QC 请求已发送，正在等待结构化返回。")
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
                handoff["message"] = "请求已写入备用传输通道；等待 ChatGPT 返回结构化结果。"
                video["bottleneck"] = "等待 ChatGPT 返回结构化生产/QC结果"
                video["auto_action"] = (
                    f"已发送；若 {RETRY_AFTER_SECONDS // 60} 分钟无返回将自动重发，"
                    f"最多 {MAX_RETRIES} 次。达到上限后停止等待并进入待我处理。"
                )
            cf._save(data)
            _set_control_truth(WAITING_RESPONSE, "内容生产/QC 请求已发送，正在等待结构化返回。")

    return {
        "pending": len(pending),
        "bridge_status": bridge.get("status"),
        "due": len(due),
        "exported": bool(exported and exported.get("exported")),
        "retry_after_seconds": RETRY_AFTER_SECONDS,
        "max_retries": MAX_RETRIES,
        "handoff": exported,
        "local_recovered": local_recovered,
    }
