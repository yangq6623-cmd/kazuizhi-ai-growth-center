"""Truthful optional-ChatGPT handoff watchdog for R8 content work.

Local-first rule:
- an active/authorized Mission is executed locally for routine planning + QC;
- realtime ChatGPT / relay / API is an optional quality enhancer, never a hard
  production dependency;
- tasks outside a Mission authorization may still use the bounded handoff path;
- no branch fabricates ChatGPT acknowledgement, publication, customers or orders.
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
    if qc.get("status") in {"passed", "rework", "not_required_for_authorized_mission"}:
        return "qc_returned"
    if video.get("status") == "等待ChatGPT质检":
        return "waiting_qc_return"
    if video.get("status") in {"等待ChatGPT策划", "退回重做"}:
        return "waiting_plan_return"
    return "local_execution"


def _set_control_truth(state_name, message):
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
        phase = _phase_for(video)
        if video.get("status") not in PENDING_STATES and phase != handoff.get("phase"):
            handoff["phase"] = phase
            handoff["response_at"] = video.get("plan_received_at") or (video.get("chatgpt_qc") or {}).get("reviewed_at") or now_iso()
            handoff["updated_at"] = now_iso()
            changed = True
    return changed


def _recover_authorized_local_plans():
    """Recover every Mission-authorized routine production task locally."""
    from promotion.local_mission_planner import mission_allows_local_content, recover_video

    data = cf._load()
    campaign_by_id = {x.get("id"): x for x in data.get("campaigns", []) if isinstance(x, dict)}
    ids = []
    for video in data.get("videos", []):
        if video.get("status") not in {"等待ChatGPT策划", "退回重做", "异常待处理"}:
            continue
        campaign = campaign_by_id.get(video.get("campaign_id"))
        if not mission_allows_local_content(campaign):
            continue
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        if video.get("status") == "异常待处理" and handoff.get("kind") not in {None, "content_production"}:
            continue
        ids.append(video.get("id"))

    recovered = []
    for video_id in ids:
        try:
            result = recover_video(video_id)
            if result:
                recovered.append(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            recovered.append({"video_id": video_id, "status": "failed", "error": str(error)[:300]})
    return recovered


def _recover_authorized_local_qc():
    try:
        from promotion.local_mission_qc_patch import recover_authorized_qc
        return recover_authorized_qc(limit=20)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        return {"processed": 0, "items": [], "error": str(error)[:300]}


def _authorized_pending(video, campaigns):
    try:
        from promotion.local_mission_planner import mission_allows_local_content
        return mission_allows_local_content(campaigns.get(video.get("campaign_id")))
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return False


def sync_chatgpt_handoffs(force=False):
    """Keep Mission work moving locally; use ChatGPT transport only when optional."""
    local_recovered = _recover_authorized_local_plans()
    local_qc = _recover_authorized_local_qc()
    data = cf._load()
    now = datetime.now().astimezone()
    changed = _mark_nonpending_truth(data)
    campaigns = {x.get("id"): x for x in data.get("campaigns", []) if isinstance(x, dict)}

    # A Mission-authorized item must never be converted into a ChatGPT-transport
    # alarm. If a local step could not advance yet, keep it as a local retry and
    # let the scheduler/video worker continue; only genuine QC risk escalates.
    local_pending = []
    remote_pending = []
    for video in data.get("videos", []):
        if video.get("status") not in PENDING_STATES:
            continue
        if _authorized_pending(video, campaigns):
            handoff = video.setdefault("chatgpt_handoff", {})
            handoff.update({
                "phase": "local_autonomy_retry",
                "message": "实时ChatGPT为可选增强；当前Mission继续由本地自治流水线重试。",
                "updated_at": now_iso(),
                "retry_count": 0,
            })
            video["bottleneck"] = "本地自治流水线正在继续处理"
            video["auto_action"] = "不等待实时ChatGPT；本地策划/生产/QC自动继续。"
            local_pending.append(video)
            changed = True
        else:
            remote_pending.append(video)

    if not remote_pending:
        if changed:
            cf._save(data)
        _clear_own_control_issue_if_resolved()
        return {
            "pending": len(local_pending),
            "remote_pending": 0,
            "exported": False,
            "reason": "authorized_mission_runs_local_first",
            "local_recovered": local_recovered,
            "local_qc": local_qc,
        }

    bridge = bridge_status()
    connected = bridge.get("status") == "connected" and bool(bridge.get("bridge_root"))
    due = []

    for video in remote_pending:
        handoff = video.setdefault("chatgpt_handoff", {})
        handoff.setdefault("kind", "content_qc" if video.get("status") == "等待ChatGPT质检" else "content_production")
        handoff.setdefault("retry_count", 0)
        handoff.setdefault("max_retries", MAX_RETRIES)
        handoff["updated_at"] = now_iso()

        if not connected:
            handoff["phase"] = "bridge_unavailable"
            handoff["bridge_status"] = bridge.get("status") or "not_connected"
            handoff["message"] = "可选ChatGPT传输未连接；此非Mission授权任务暂缓。"
            video["bottleneck"] = "可选ChatGPT交接不可用"
            video["auto_action"] = "系统继续检查传输通道；Mission授权任务不受此状态影响。"
            _set_control_truth(DEGRADED, "可选内容交接通道不可用；本地Mission自治继续运行。")
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
            video["bottleneck"] = "非Mission授权任务的ChatGPT请求连续重发仍未返回"
            video["auto_action"] = "已停止无限等待；此任务需要人工确认是否继续。Mission自治任务不会走到这里。"
            _set_control_truth(HUMAN_ACTION_REQUIRED, f"非Mission授权内容任务已重试 {MAX_RETRIES} 次仍无返回。")
            changed = True
        else:
            handoff["phase"] = "waiting_response"
            handoff["bridge_status"] = "connected"
            handoff["message"] = "可选请求已发送，等待结构化结果。"
            _set_control_truth(WAITING_RESPONSE, "可选内容请求已发送；本地Mission自治不受影响。")
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
                handoff["message"] = "可选请求已发送；等待结构化结果。"
                video["bottleneck"] = "等待可选ChatGPT返回"
                video["auto_action"] = f"若 {RETRY_AFTER_SECONDS // 60} 分钟无返回将自动重发，最多 {MAX_RETRIES} 次。"
            cf._save(data)
            _set_control_truth(WAITING_RESPONSE, "可选内容请求已发送；本地Mission自治不受影响。")

    return {
        "pending": len(local_pending) + len(remote_pending),
        "remote_pending": len(remote_pending),
        "bridge_status": bridge.get("status"),
        "due": len(due),
        "exported": bool(exported and exported.get("exported")),
        "retry_after_seconds": RETRY_AFTER_SECONDS,
        "max_retries": MAX_RETRIES,
        "handoff": exported,
        "local_recovered": local_recovered,
        "local_qc": local_qc,
    }
