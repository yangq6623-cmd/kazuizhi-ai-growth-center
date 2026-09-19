"""R8 complete growth-operations workflow.

This module implements the durable, truthful control plane required by the R8
handoff: public-signal intake, one-account routing, growth IDs, eight-role
content briefs, local-video orchestration, owner-gated publishing, unified
conversations/leads, attribution checkpoints and learning feedback.

It deliberately does not pretend an external platform, GPU model or business
source is connected. External execution becomes available only after a real
connector reports a verified receipt.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.r8_control import PLATFORMS, control_status
from core.storage import now_iso, read_json, write_json


STATE_PATH = "r8/growth_ops.json"
SCHEMA = "kazuizhi-r8-growth-ops/v1"
_LOCK = threading.RLock()

AUTOMATION_LEVELS = {"L1", "L2", "L3", "L4"}
SIGNAL_STATUSES = {"new", "routed", "ignored", "converted"}
LEAD_STAGES = {"new", "engaged", "qualified", "waiting_user", "follow_up_due", "converted", "closed", "human_required"}
CONTENT_GOALS = {"brand", "education", "search", "conversion", "recruitment"}
CHECKPOINTS = {"24h", "72h", "7d"}
RISK_LEVELS = {"low", "normal", "attention", "high"}

EIGHT_ROLES = (
    ("market_intelligence", "市场情报员"),
    ("seo_geo", "SEO/GEO 增长员"),
    ("content_operator", "内容运营员"),
    ("social_operator", "社媒运营员"),
    ("short_video", "短视频运营员"),
    ("local_growth", "本地增长员"),
    ("conversion", "用户转化员"),
    ("data_review", "数据复盘员"),
)


def _default_state():
    return {
        "schema": SCHEMA,
        "delivery": {
            "version": "R8 Final",
            "phase": "R8-08",
            "modules": ["R8-00", "R8-01", "R8-02", "R8-03", "R8-04", "R8-05", "R8-06", "R8-07", "R8-08"],
            "automation_default": "L2",
            "pilot_region": "涟水",
            "truth_policy": "未连接的外部平台、GPU 模型和经营数据必须明确显示未配置，不得伪造成功",
        },
        "video_worker": {
            "backend": "local_rtx3060_worker",
            "configured": False,
            "max_vram_gb": 9.5,
            "reserve_vram_gb": 2.5,
            "sequential_candidates": True,
            "candidate_count": 3,
            "oom_policy": "降低分辨率/帧数/镜头并停止同参数无限重试",
            "updated_at": None,
        },
        "signals": [],
        "growth_cases": [],
        "content_jobs": [],
        "video_jobs": [],
        "publish_jobs": [],
        "conversations": [],
        "messages": [],
        "leads": [],
        "attribution": [],
        "metric_snapshots": [],
        "content_genes": [],
        "learning_cycles": [],
        "audit": [],
        "updated_at": now_iso(),
    }


def _state():
    value = read_json(STATE_PATH, None)
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        value = _default_state()
        write_json(STATE_PATH, value)
    for key, default in _default_state().items():
        value.setdefault(key, default)
    delivery = value.setdefault("delivery", {})
    for key, default in _default_state()["delivery"].items():
        delivery.setdefault(key, default)
    return value


def _save(state):
    state["updated_at"] = now_iso()
    write_json(STATE_PATH, state)
    return state


def _clean_text(value, name, maximum=240, required=True):
    text = " ".join(str(value or "").split()).strip()
    if required and not text:
        raise ValueError(f"{name}不能为空")
    if len(text) > maximum:
        raise ValueError(f"{name}不能超过 {maximum} 字")
    return text


def _enum(value, allowed, name, default=None):
    result = str(value or default or "").strip()
    if result not in allowed:
        raise ValueError(f"{name}不支持：{result}")
    return result


def _number(value, name):
    try:
        number = float(value or 0)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name}必须是数字") from error
    if number < 0:
        raise ValueError(f"{name}不能小于 0")
    return int(number) if number.is_integer() else round(number, 4)


def _id(prefix):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"


def _find(items, key, value, label):
    item = next((row for row in items if row.get(key) == value), None)
    if not item:
        raise ValueError(f"未找到{label}")
    return item


def _audit(state, kind, entity_id, detail, actor="r8"):
    state["audit"].append({
        "id": _id("AUD"),
        "at": now_iso(),
        "kind": kind,
        "entity_id": entity_id,
        "actor": _clean_text(actor, "操作人", 80, required=False) or "r8",
        "detail": _clean_text(detail, "审计说明", 500),
    })
    state["audit"] = state["audit"][-1000:]


def _secret_guard(payload):
    forbidden = {"password", "passcode", "secret", "access_token", "refresh_token", "cookie"}
    lowered = {str(key).lower() for key in (payload or {}).keys()}
    if lowered & forbidden:
        raise ValueError("普通 R8 接口不接收密码、验证码、Cookie 或平台令牌")


def _platform(value):
    platform = str(value or "").strip()
    if platform not in PLATFORMS:
        raise ValueError("请选择已登记的平台")
    return platform


def _dedupe_key(payload):
    supplied = str(payload.get("dedupe_key") or "").strip()
    if supplied:
        return supplied[:160]
    raw = "|".join([
        str(payload.get("platform") or ""),
        str(payload.get("source_id") or ""),
        str(payload.get("source_url") or ""),
        str(payload.get("summary") or ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _gpu_probe():
    command = shutil.which("nvidia-smi")
    result = {"detected": False, "name": None, "memory_total_mb": None, "driver": None}
    if not command:
        return result
    try:
        completed = subprocess.run(
            [command, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=4,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        first = completed.stdout.strip().splitlines()[0]
        name, memory, driver = [part.strip() for part in first.split(",", 2)]
        result.update(detected=True, name=name, memory_total_mb=int(float(memory)), driver=driver)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return result


def dashboard():
    with _LOCK:
        state = _state()
        control = control_status()
        gpu = _gpu_probe()
        worker = dict(state["video_worker"])
        worker["hardware"] = gpu
        devices = control.get("devices") or []
        accounts = control.get("accounts") or []
        connected_devices = [row for row in devices if row.get("connection") == "connected" and row.get("probe_source") == "adb"]
        authorized_accounts = [row for row in accounts if row.get("login_status") == "authorized"]
        connectors = []
        for platform_id, platform_name in PLATFORMS.items():
            rows = [row for row in accounts if row.get("platform") == platform_id]
            connectors.append({
                "id": platform_id,
                "name": platform_name,
                "configured": bool(rows),
                "authorized": sum(1 for row in rows if row.get("login_status") == "authorized"),
                "state": "ready" if any(row.get("login_status") == "authorized" for row in rows) else "not_configured",
            })
        counts = {key: len(state[key]) for key in (
            "signals", "growth_cases", "content_jobs", "video_jobs", "publish_jobs",
            "conversations", "leads", "attribution", "learning_cycles",
        )}
        gates = [
            {"id": "Gate 0", "name": "安全与总控", "software": "ready", "live": "ready"},
            {"id": "Gate 1", "name": "单真机", "software": "ready", "live": "ready" if connected_devices else "pending_device"},
            {"id": "Gate 2", "name": "平台情报雷达", "software": "ready", "live": "ready" if authorized_accounts else "pending_connector"},
            {"id": "Gate 3", "name": "增长ID与内容策划", "software": "ready", "live": "ready" if state["growth_cases"] else "waiting_first_case"},
            {"id": "Gate 4", "name": "3060视频工厂", "software": "ready", "live": "ready" if worker.get("configured") and gpu.get("detected") else "pending_worker"},
            {"id": "Gate 5", "name": "人工审核与真实发布", "software": "ready", "live": "ready" if any(row.get("status") == "published" for row in state["publish_jobs"]) else "waiting_first_receipt"},
            {"id": "Gate 6", "name": "消息与线索", "software": "ready", "live": "ready" if state["conversations"] else "waiting_first_message"},
            {"id": "Gate 7", "name": "24h/72h/7天归因", "software": "ready", "live": "ready" if state["metric_snapshots"] else "waiting_metrics"},
            {"id": "Gate 8", "name": "学习回写", "software": "ready", "live": "ready" if state["learning_cycles"] else "waiting_learning_cycle"},
        ]
        return {
            "schema": SCHEMA,
            "delivery": state["delivery"],
            "counts": counts,
            "gates": gates,
            "video_worker": worker,
            "connectors": connectors,
            "devices": {"registered": len(devices), "connected": len(connected_devices)},
            "accounts": {"registered": len(accounts), "authorized": len(authorized_accounts)},
            "recent_audit": list(reversed(state["audit"][-30:])),
            "updated_at": state["updated_at"],
        }


def list_collection(name):
    allowed = {
        "signals", "growth_cases", "content_jobs", "video_jobs", "publish_jobs",
        "conversations", "messages", "leads", "attribution", "metric_snapshots",
        "content_genes", "learning_cycles", "audit",
    }
    if name not in allowed:
        raise ValueError("不支持的数据集合")
    with _LOCK:
        state = _state()
        return {"items": list(reversed(state[name])), "count": len(state[name]), "updated_at": state["updated_at"]}


def ingest_signal(payload):
    payload = payload or {}
    _secret_guard(payload)
    platform = _platform(payload.get("platform"))
    summary = _clean_text(payload.get("summary"), "需求内容", 1000)
    source_url = _clean_text(payload.get("source_url"), "来源链接", 500, required=False)
    source_id = _clean_text(payload.get("source_id"), "来源 ID", 160, required=False)
    if not source_url and not source_id:
        raise ValueError("来源链接和来源 ID 至少填写一项")
    item = {
        "signal_id": _id("SIG"),
        "platform": platform,
        "platform_name": PLATFORMS[platform],
        "source_url": source_url or None,
        "source_id": source_id or None,
        "author_public_id": _clean_text(payload.get("author_public_id"), "公开用户标识", 120, required=False) or None,
        "published_at": _clean_text(payload.get("published_at"), "发布时间", 80, required=False) or None,
        "detected_at": now_iso(),
        "region": _clean_text(payload.get("region"), "地区", 80),
        "service_category": _clean_text(payload.get("service_category"), "服务类型", 120),
        "intent_level": _enum(payload.get("intent_level"), {"low", "medium", "high"}, "意向等级", "medium"),
        "urgency": _enum(payload.get("urgency"), {"low", "normal", "urgent"}, "紧急程度", "normal"),
        "sentiment": _enum(payload.get("sentiment"), {"negative", "neutral", "positive"}, "情绪", "neutral"),
        "risk_level": _enum(payload.get("risk_level"), RISK_LEVELS, "风险等级", "normal"),
        "summary": summary,
        "recommended_action": _enum(payload.get("recommended_action"), {"comment", "reply", "dm", "ignore", "human"}, "推荐动作", "reply"),
        "dedupe_key": _dedupe_key(payload),
        "matched_account_id": None,
        "route_state": "not_routed",
        "status": "new",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    with _LOCK:
        state = _state()
        duplicate = next((row for row in state["signals"] if row.get("dedupe_key") == item["dedupe_key"]), None)
        if duplicate:
            return {"created": False, "duplicate": True, "item": duplicate}
        state["signals"].append(item)
        _audit(state, "signal_ingested", item["signal_id"], f"保存公开需求信号：{summary[:120]}")
        _save(state)
        return {"created": True, "duplicate": False, "item": item}


def route_signal(payload):
    payload = payload or {}
    signal_id = _clean_text(payload.get("signal_id"), "signal_id", 80)
    with _LOCK:
        state = _state()
        signal = _find(state["signals"], "signal_id", signal_id, "需求信号")
        accounts = control_status().get("accounts") or []
        candidates = []
        for account in accounts:
            if account.get("platform") != signal["platform"]:
                continue
            score = 0
            if account.get("region") == signal["region"]:
                score += 4
            if account.get("service_category") == signal["service_category"]:
                score += 5
            if account.get("role") == "brand":
                score += 1
            if account.get("login_status") == "authorized":
                score += 2
            if account.get("automation_paused") or account.get("risk_level") in {"attention", "high"}:
                score -= 100
            candidates.append((score, account))
        candidates.sort(key=lambda pair: (-pair[0], pair[1].get("account_id", "")))
        selected = candidates[0][1] if candidates and candidates[0][0] > -50 else None
        signal["matched_account_id"] = selected.get("account_id") if selected else None
        signal["route_state"] = (
            "ready" if selected and selected.get("login_status") == "authorized"
            else "candidate_needs_authorization" if selected else "no_matching_account"
        )
        signal["status"] = "routed" if selected else "new"
        signal["updated_at"] = now_iso()
        _audit(state, "signal_routed", signal_id, f"路由结果：{signal['route_state']}；账号：{signal['matched_account_id'] or '无'}")
        _save(state)
        return {"signal": signal, "account": selected, "candidate_count": len(candidates)}


def create_growth_case(payload):
    payload = payload or {}
    signal_id = _clean_text(payload.get("signal_id"), "signal_id", 80)
    with _LOCK:
        state = _state()
        signal = _find(state["signals"], "signal_id", signal_id, "需求信号")
        existing = next((row for row in state["growth_cases"] if row.get("signal_id") == signal_id), None)
        if existing:
            return {"created": False, "item": existing}
        item = {
            "growth_id": _id("GROWTH"),
            "signal_id": signal_id,
            "source": {"platform": signal["platform"], "url": signal.get("source_url"), "source_id": signal.get("source_id")},
            "region": signal["region"],
            "service_category": signal["service_category"],
            "target_user": _clean_text(payload.get("target_user"), "目标用户", 160, required=False) or "本地真实需求用户",
            "hypothesis": _clean_text(payload.get("hypothesis"), "增长假设", 500, required=False) or f"围绕“{signal['summary'][:80]}”提供真实帮助，可形成有效咨询机会",
            "business_goal": _enum(payload.get("business_goal"), CONTENT_GOALS, "业务目标", "conversion"),
            "status": "planning",
            "content_job_id": None,
            "publish_job_id": None,
            "conclusion": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        state["growth_cases"].append(item)
        _audit(state, "growth_case_created", item["growth_id"], f"从 {signal_id} 建立唯一增长 ID")
        _save(state)
        return {"created": True, "item": item}


def create_content_brief(payload):
    payload = payload or {}
    growth_id = _clean_text(payload.get("growth_id"), "growth_id", 80)
    with _LOCK:
        state = _state()
        growth = _find(state["growth_cases"], "growth_id", growth_id, "增长任务")
        signal = _find(state["signals"], "signal_id", growth["signal_id"], "来源信号")
        if growth.get("content_job_id"):
            existing = _find(state["content_jobs"], "content_id", growth["content_job_id"], "内容任务")
            return {"created": False, "item": existing}
        region = growth["region"]
        service = growth["service_category"]
        evidence = signal["summary"]
        committee = [
            {"role_id": "market_intelligence", "role": "市场情报员", "recommendation": f"来源为 {signal['platform_name']} 公开需求，先验证同类问题是否重复出现。"},
            {"role_id": "seo_geo", "role": "SEO/GEO 增长员", "recommendation": f"标题必须保留“{region}”与“{service}”的真实地域和服务表达。"},
            {"role_id": "content_operator", "role": "内容运营员", "recommendation": "先解释问题和排查方法，再说明可提供的服务，不写空泛广告。"},
            {"role_id": "social_operator", "role": "社媒运营员", "recommendation": f"按 {signal['platform_name']} 表达习惯重写，禁止跨平台原样复制。"},
            {"role_id": "short_video", "role": "短视频运营员", "recommendation": "前三秒直接呈现用户问题，镜头围绕现场、判断、解决路径展开。"},
            {"role_id": "local_growth", "role": "本地增长员", "recommendation": f"只承诺 {region} 已开放且可履约的真实服务范围。"},
            {"role_id": "conversion", "role": "用户转化员", "recommendation": "CTA 先询问地区、时间和故障情况；用户明确需要时再引导服务入口。"},
            {"role_id": "data_review", "role": "数据复盘员", "recommendation": "发布后按 24h、72h、7天保存真实回执与转化数据。"},
        ]
        item = {
            "content_id": _id("CONTENT"),
            "growth_id": growth_id,
            "platform": signal["platform"],
            "account_id": signal.get("matched_account_id"),
            "region": region,
            "service_category": service,
            "content_goal": growth["business_goal"],
            "source_evidence": evidence,
            "target_user": growth["target_user"],
            "title_candidates": [
                f"{region}{service}遇到这种情况先别急，先检查这三点",
                f"{region}需要{service}时，先把这几个问题问清楚",
                f"一个真实{service}问题，应该怎样判断和处理",
            ],
            "first_three_seconds": f"直接展示问题：{evidence[:100]}",
            "body_structure": ["真实问题", "安全排查", "常见原因", "服务边界", "下一步"],
            "cta": "如确实需要本地服务，请说明地区、时间和具体情况，再进入人工或服务入口。",
            "committee": committee,
            "approval_state": "pending",
            "approval_note": None,
            "approved_by": None,
            "approved_at": None,
            "publish_state": "not_scheduled",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        state["content_jobs"].append(item)
        growth["content_job_id"] = item["content_id"]
        growth["status"] = "content_pending_approval"
        growth["updated_at"] = now_iso()
        _audit(state, "content_committee_completed", item["content_id"], "八员工内容委员会已形成可审核任务单")
        _save(state)
        return {"created": True, "item": item}


def review_content(payload):
    payload = payload or {}
    content_id = _clean_text(payload.get("content_id"), "content_id", 80)
    action = _enum(payload.get("action"), {"approve", "reject", "revise"}, "审核动作")
    reviewer = _clean_text(payload.get("reviewer"), "审核人", 80, required=False) or "owner"
    note = _clean_text(payload.get("note"), "审核说明", 500, required=False)
    with _LOCK:
        state = _state()
        item = _find(state["content_jobs"], "content_id", content_id, "内容任务")
        item["approval_state"] = {"approve": "approved", "reject": "rejected", "revise": "revision_requested"}[action]
        item["approval_note"] = note or None
        item["approved_by"] = reviewer
        item["approved_at"] = now_iso()
        item["updated_at"] = now_iso()
        growth = _find(state["growth_cases"], "growth_id", item["growth_id"], "增长任务")
        growth["status"] = "content_approved" if action == "approve" else item["approval_state"]
        growth["updated_at"] = now_iso()
        _audit(state, "content_reviewed", content_id, f"内容审核：{item['approval_state']}；{note or '无补充说明'}", reviewer)
        _save(state)
        return item


def configure_video_worker(payload):
    payload = payload or {}
    enabled = bool(payload.get("configured"))
    with _LOCK:
        state = _state()
        worker = state["video_worker"]
        model_path = _clean_text(payload.get("model_path"), "模型路径", 500, required=False) or None
        output_root = _clean_text(payload.get("output_root"), "输出目录", 500, required=False) or None
        if enabled:
            if not model_path or not Path(model_path).exists():
                raise ValueError("启用视频 Worker 前必须选择真实存在的本地模型路径")
            if not output_root or not Path(output_root).is_dir():
                raise ValueError("启用视频 Worker 前必须选择真实存在的成片输出目录")
        worker["configured"] = enabled
        worker["model_path"] = model_path
        worker["output_root"] = output_root
        worker["updated_at"] = now_iso()
        _audit(state, "video_worker_configured", "video-worker", f"本地视频 Worker：{'已配置' if enabled else '未配置'}")
        _save(state)
        return dict(worker, hardware=_gpu_probe())


def create_video_job(payload):
    payload = payload or {}
    content_id = _clean_text(payload.get("content_id"), "content_id", 80)
    with _LOCK:
        state = _state()
        content = _find(state["content_jobs"], "content_id", content_id, "内容任务")
        if content.get("approval_state") != "approved":
            raise ValueError("内容任务必须先由老板审核通过")
        existing = next((row for row in state["video_jobs"] if row.get("content_id") == content_id and row.get("status") not in {"failed", "rejected"}), None)
        if existing:
            return {"created": False, "item": existing}
        worker = state["video_worker"]
        shots = [
            {"shot": 1, "purpose": "前三秒呈现真实问题", "candidate_count": 3, "selected": None},
            {"shot": 2, "purpose": "解释排查与判断过程", "candidate_count": 3, "selected": None},
            {"shot": 3, "purpose": "说明服务边界与下一步", "candidate_count": 3, "selected": None},
        ]
        item = {
            "video_id": _id("VIDEO"),
            "content_id": content_id,
            "growth_id": content["growth_id"],
            "status": "queued" if worker.get("configured") and _gpu_probe().get("detected") else "waiting_worker",
            "worker_backend": worker["backend"],
            "gpu_budget": {"max_vram_gb": worker["max_vram_gb"], "reserve_vram_gb": worker["reserve_vram_gb"]},
            "shots": shots,
            "output_path": None,
            "quality": None,
            "owner_approval": "pending",
            "failure": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        state["video_jobs"].append(item)
        _audit(state, "video_job_created", item["video_id"], f"视频任务状态：{item['status']}；按镜头串行生成候选")
        _save(state)
        return {"created": True, "item": item}


def update_video_job(payload):
    payload = payload or {}
    video_id = _clean_text(payload.get("video_id"), "video_id", 80)
    action = _enum(payload.get("action"), {"start", "complete", "approve", "reject", "fail"}, "视频动作")
    with _LOCK:
        state = _state()
        item = _find(state["video_jobs"], "video_id", video_id, "视频任务")
        if action == "start":
            if not state["video_worker"].get("configured") or not _gpu_probe().get("detected"):
                raise ValueError("本机 RTX 视频 Worker 尚未配置或未检测到可用 NVIDIA GPU")
            item["status"] = "running"
        elif action == "complete":
            output_path = _clean_text(payload.get("output_path"), "成片路径", 500)
            item["output_path"] = output_path
            item["quality"] = {
                "visual": _number(payload.get("visual", 0), "画面评分"),
                "script": _number(payload.get("script", 0), "脚本一致性评分"),
                "subtitle": _number(payload.get("subtitle", 0), "字幕评分"),
                "risk": _number(payload.get("risk", 0), "风险评分"),
            }
            item["status"] = "awaiting_owner_review"
        elif action == "approve":
            if item.get("status") != "awaiting_owner_review":
                raise ValueError("只有已生成并等待审核的成片可以确认发布")
            item["owner_approval"] = "approved"
            item["status"] = "approved"
        elif action == "reject":
            item["owner_approval"] = "rejected"
            item["status"] = "rejected"
            item["failure"] = _clean_text(payload.get("reason"), "退回原因", 500)
        else:
            item["status"] = "failed"
            item["failure"] = _clean_text(payload.get("reason"), "失败原因", 500)
        item["updated_at"] = now_iso()
        _audit(state, "video_job_updated", video_id, f"视频任务动作：{action}；状态：{item['status']}", payload.get("actor") or "r8")
        _save(state)
        return item


def schedule_publish(payload):
    payload = payload or {}
    content_id = _clean_text(payload.get("content_id"), "content_id", 80)
    account_id = _clean_text(payload.get("account_id"), "account_id", 180)
    if not bool(payload.get("owner_approved")):
        raise ValueError("发布必须由老板点击确认发布")
    with _LOCK:
        state = _state()
        content = _find(state["content_jobs"], "content_id", content_id, "内容任务")
        if content.get("approval_state") != "approved":
            raise ValueError("内容尚未审核通过")
        control = control_status()
        account = _find(control.get("accounts") or [], "account_id", account_id, "平台账号")
        if account.get("login_status") != "authorized":
            raise ValueError("平台账号尚未在真实手机完成人工登录/授权")
        if account.get("platform") != content.get("platform"):
            raise ValueError("发布账号平台与内容策划平台不一致")
        video_id = _clean_text(payload.get("video_id"), "video_id", 80, required=False) or None
        if video_id:
            video = _find(state["video_jobs"], "video_id", video_id, "视频任务")
            if video.get("owner_approval") != "approved":
                raise ValueError("视频成片尚未由老板确认发布")
        item = {
            "publish_id": _id("PUB"),
            "growth_id": content["growth_id"],
            "content_id": content_id,
            "video_id": video_id,
            "platform": account["platform"],
            "account_id": account_id,
            "device_id": account["device_id"],
            "scheduled_at": _clean_text(payload.get("scheduled_at"), "计划发布时间", 80, required=False) or now_iso(),
            "owner_approved": True,
            "status": "queued",
            "connector_state": "waiting_real_execution",
            "receipt": None,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        state["publish_jobs"].append(item)
        content["publish_state"] = "queued"
        content["updated_at"] = now_iso()
        growth = _find(state["growth_cases"], "growth_id", content["growth_id"], "增长任务")
        growth["publish_job_id"] = item["publish_id"]
        growth["status"] = "publish_queued"
        growth["updated_at"] = now_iso()
        _audit(state, "publish_authorized", item["publish_id"], "老板已确认发布；等待真实平台执行和回执", payload.get("reviewer") or "owner")
        _save(state)
        return item


def record_publish_receipt(payload):
    payload = payload or {}
    publish_id = _clean_text(payload.get("publish_id"), "publish_id", 80)
    result = _enum(payload.get("result"), {"success", "failed", "submitted"}, "发布结果")
    with _LOCK:
        state = _state()
        item = _find(state["publish_jobs"], "publish_id", publish_id, "发布任务")
        receipt = {
            "result": result,
            "platform_content_id": _clean_text(payload.get("platform_content_id"), "平台内容 ID", 240, required=False) or None,
            "url": _clean_text(payload.get("url"), "平台 URL", 500, required=False) or None,
            "executed_at": _clean_text(payload.get("executed_at"), "执行时间", 80, required=False) or now_iso(),
            "executed_by": _enum(payload.get("executed_by"), {"official_api", "real_device", "human"}, "执行来源"),
            "error": _clean_text(payload.get("error"), "失败原因", 500, required=False) or None,
        }
        if result == "success" and (not receipt["platform_content_id"] or not receipt["url"]):
            raise ValueError("发布成功必须保存真实平台内容 ID 和 URL")
        if result == "failed" and not receipt["error"]:
            raise ValueError("发布失败必须保存失败原因")
        item["receipt"] = receipt
        item["status"] = {"success": "published", "failed": "failed", "submitted": "submitted_waiting_confirmation"}[result]
        item["connector_state"] = "verified_receipt" if result == "success" else item["status"]
        item["updated_at"] = now_iso()
        content = _find(state["content_jobs"], "content_id", item["content_id"], "内容任务")
        content["publish_state"] = item["status"]
        content["updated_at"] = now_iso()
        growth = _find(state["growth_cases"], "growth_id", item["growth_id"], "增长任务")
        growth["status"] = "published" if result == "success" else item["status"]
        growth["updated_at"] = now_iso()
        _audit(state, "publish_receipt", publish_id, f"真实发布回执：{result}；{receipt['url'] or receipt['error'] or '待确认'}", receipt["executed_by"])
        _save(state)
        return item


def ingest_message(payload):
    payload = payload or {}
    _secret_guard(payload)
    platform = _platform(payload.get("platform"))
    account_id = _clean_text(payload.get("account_id"), "account_id", 180)
    user_ref = _clean_text(payload.get("user_ref"), "公开用户标识", 160)
    content = _clean_text(payload.get("content"), "消息内容", 2000)
    direction = _enum(payload.get("direction"), {"inbound", "outbound"}, "消息方向", "inbound")
    kind = _enum(payload.get("kind"), {"comment", "reply", "dm", "mention"}, "消息类型", "comment")
    accounts = control_status().get("accounts") or []
    account = next((row for row in accounts if row.get("account_id") == account_id), None)
    if not account or account.get("platform") != platform:
        raise ValueError("消息必须归属已登记且平台一致的真实账号")
    with _LOCK:
        state = _state()
        conversation = next((row for row in state["conversations"] if row.get("platform") == platform and row.get("user_ref") == user_ref), None)
        if conversation and direction == "outbound" and conversation.get("do_not_contact"):
            raise ValueError("用户已明确停止联系，禁止跨账号继续触达")
        if conversation and conversation.get("account_id") != account_id:
            alternates = conversation.setdefault("alternate_account_ids", [])
            if account_id not in alternates:
                alternates.append(account_id)
        if not conversation:
            conversation = {
                "conversation_id": _id("CONV"),
                "platform": platform,
                "account_id": account_id,
                "user_ref": user_ref,
                "state": "new",
                "risk_level": "normal",
                "do_not_contact": False,
                "lead_id": None,
                "last_message_at": now_iso(),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            state["conversations"].append(conversation)
        lower = content.lower()
        human_terms = ("退款", "投诉", "赔偿", "银行卡", "身份证", "支付", "纠纷", "法律")
        if any(term in lower for term in human_terms):
            conversation["state"] = "human_required"
            conversation["risk_level"] = "high"
        message = {
            "message_id": _id("MSG"),
            "conversation_id": conversation["conversation_id"],
            "direction": direction,
            "kind": kind,
            "content": content,
            "receipt_id": _clean_text(payload.get("receipt_id"), "消息回执", 240, required=False) or None,
            "sent_at": _clean_text(payload.get("sent_at"), "消息时间", 80, required=False) or now_iso(),
            "source": _enum(payload.get("source"), {"official_api", "real_device", "human_import"}, "消息来源", "human_import"),
        }
        state["messages"].append(message)
        conversation["last_message_at"] = message["sent_at"]
        conversation["updated_at"] = now_iso()
        _audit(state, "message_ingested", message["message_id"], f"{kind}/{direction} 已进入统一会话；状态：{conversation['state']}")
        _save(state)
        return {"conversation": conversation, "message": message}


def update_conversation(payload):
    payload = payload or {}
    conversation_id = _clean_text(payload.get("conversation_id"), "conversation_id", 80)
    state_value = _enum(payload.get("state"), LEAD_STAGES, "会话状态")
    with _LOCK:
        state = _state()
        item = _find(state["conversations"], "conversation_id", conversation_id, "会话")
        item["state"] = state_value
        if "do_not_contact" in payload:
            item["do_not_contact"] = bool(payload.get("do_not_contact"))
            if item["do_not_contact"]:
                item["state"] = "closed"
        item["updated_at"] = now_iso()
        _audit(state, "conversation_updated", conversation_id, f"会话状态：{item['state']}；停止联系：{item['do_not_contact']}", payload.get("actor") or "owner")
        _save(state)
        return item


def upsert_lead(payload):
    payload = payload or {}
    lead_id = _clean_text(payload.get("lead_id"), "lead_id", 80, required=False)
    conversation_id = _clean_text(payload.get("conversation_id"), "conversation_id", 80, required=False)
    stage = _enum(payload.get("stage"), LEAD_STAGES, "线索阶段", "new")
    with _LOCK:
        state = _state()
        item = next((row for row in state["leads"] if row.get("lead_id") == lead_id), None) if lead_id else None
        conversation = _find(state["conversations"], "conversation_id", conversation_id, "会话") if conversation_id else None
        if not item:
            item = {
                "lead_id": _id("LEAD"),
                "conversation_id": conversation_id or None,
                "signal_id": _clean_text(payload.get("signal_id"), "signal_id", 80, required=False) or None,
                "platform": (conversation or {}).get("platform") or _platform(payload.get("platform")),
                "account_id": (conversation or {}).get("account_id") or _clean_text(payload.get("account_id"), "account_id", 180),
                "region": _clean_text(payload.get("region"), "地区", 80),
                "service_category": _clean_text(payload.get("service_category"), "服务类型", 120),
                "stage": stage,
                "next_follow_up_at": _clean_text(payload.get("next_follow_up_at"), "下次跟进时间", 80, required=False) or None,
                "do_not_contact": False,
                "order_id": None,
                "first_touch_at": now_iso(),
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            state["leads"].append(item)
            if conversation:
                conversation["lead_id"] = item["lead_id"]
                conversation["state"] = stage
                conversation["updated_at"] = now_iso()
        else:
            item["stage"] = stage
            item["next_follow_up_at"] = _clean_text(payload.get("next_follow_up_at"), "下次跟进时间", 80, required=False) or item.get("next_follow_up_at")
            if "do_not_contact" in payload:
                item["do_not_contact"] = bool(payload.get("do_not_contact"))
                if item["do_not_contact"]:
                    item["stage"] = "closed"
            item["updated_at"] = now_iso()
        _audit(state, "lead_upserted", item["lead_id"], f"线索阶段：{item['stage']}；来源平台：{item['platform']}", payload.get("actor") or "owner")
        _save(state)
        return item


def record_attribution(payload):
    payload = payload or {}
    lead_id = _clean_text(payload.get("lead_id"), "lead_id", 80)
    order_id = _clean_text(payload.get("order_id"), "订单 ID", 160)
    source = _enum(payload.get("source"), {"manual_confirmation", "verified_readonly_business_source"}, "归因来源")
    with _LOCK:
        state = _state()
        lead = _find(state["leads"], "lead_id", lead_id, "线索")
        existing = next((row for row in state["attribution"] if row.get("lead_id") == lead_id and row.get("order_id") == order_id), None)
        if existing:
            return {"created": False, "item": existing}
        item = {
            "attribution_id": _id("ATTR"),
            "lead_id": lead_id,
            "order_id": order_id,
            "source": source,
            "platform": lead["platform"],
            "account_id": lead["account_id"],
            "service_category": lead["service_category"],
            "region": lead["region"],
            "order_status": _enum(payload.get("order_status"), {"created", "accepted", "completed", "cancelled"}, "订单状态", "created"),
            "recorded_at": now_iso(),
        }
        state["attribution"].append(item)
        lead["order_id"] = order_id
        lead["stage"] = "converted"
        lead["updated_at"] = now_iso()
        _audit(state, "attribution_recorded", item["attribution_id"], f"线索 {lead_id} 关联订单 {order_id}；只读/人工确认，不执行资金动作")
        _save(state)
        return {"created": True, "item": item}


def record_metrics(payload):
    payload = payload or {}
    publish_id = _clean_text(payload.get("publish_id"), "publish_id", 80)
    checkpoint = _enum(payload.get("checkpoint"), CHECKPOINTS, "复盘时间点")
    with _LOCK:
        state = _state()
        publish = _find(state["publish_jobs"], "publish_id", publish_id, "发布任务")
        if publish.get("status") != "published":
            raise ValueError("只有带真实成功回执的发布任务可以记录效果")
        values = {name: _number(payload.get(name, 0), name) for name in (
            "impressions", "plays", "completions", "likes", "comments", "saves", "shares", "dms", "consultations", "orders", "completed_orders",
        )}
        existing = next((row for row in state["metric_snapshots"] if row.get("publish_id") == publish_id and row.get("checkpoint") == checkpoint), None)
        if existing:
            existing["metrics"] = values
            existing["source"] = _enum(payload.get("source"), {"official_api", "platform_export", "manual_verified"}, "指标来源")
            existing["recorded_at"] = now_iso()
            item = existing
        else:
            item = {
                "snapshot_id": _id("METRIC"),
                "publish_id": publish_id,
                "growth_id": publish["growth_id"],
                "checkpoint": checkpoint,
                "metrics": values,
                "source": _enum(payload.get("source"), {"official_api", "platform_export", "manual_verified"}, "指标来源"),
                "recorded_at": now_iso(),
            }
            state["metric_snapshots"].append(item)
        _audit(state, "metrics_recorded", item["snapshot_id"], f"{checkpoint} 真实指标已保存；来源：{item['source']}")
        _save(state)
        return item


def run_learning_cycle(payload=None):
    payload = payload or {}
    with _LOCK:
        state = _state()
        if not state["metric_snapshots"]:
            raise ValueError("尚无真实 24h/72h/7天指标，不能生成学习结论")
        by_growth = {}
        for snapshot in state["metric_snapshots"]:
            totals = by_growth.setdefault(snapshot["growth_id"], {"consultations": 0, "orders": 0, "completed_orders": 0, "engagement": 0})
            metrics = snapshot["metrics"]
            totals["consultations"] += metrics.get("consultations", 0)
            totals["orders"] += metrics.get("orders", 0)
            totals["completed_orders"] += metrics.get("completed_orders", 0)
            totals["engagement"] += metrics.get("likes", 0) + metrics.get("comments", 0) + metrics.get("saves", 0) + metrics.get("shares", 0)
        ranked = sorted(by_growth.items(), key=lambda row: (row[1]["completed_orders"], row[1]["orders"], row[1]["consultations"], row[1]["engagement"]), reverse=True)
        best_growth_id, best = ranked[0]
        growth = _find(state["growth_cases"], "growth_id", best_growth_id, "增长任务")
        content = next((row for row in state["content_jobs"] if row.get("growth_id") == best_growth_id), None)
        decision = "保留并继续小规模验证" if best["consultations"] or best["orders"] else "改写并重新测试，不扩大发布"
        cycle = {
            "cycle_id": _id("LEARN"),
            "growth_id": best_growth_id,
            "evidence": best,
            "decision": decision,
            "next_change": _clean_text(payload.get("next_change"), "下一轮调整", 500, required=False) or "根据真实结果调整标题、前三秒、服务表达和 CTA",
            "created_at": now_iso(),
        }
        state["learning_cycles"].append(cycle)
        gene = {
            "gene_id": _id("GENE"),
            "growth_id": best_growth_id,
            "region": growth["region"],
            "service_category": growth["service_category"],
            "platform": (content or {}).get("platform"),
            "title": ((content or {}).get("title_candidates") or [None])[0],
            "evidence": best,
            "decision": decision,
            "created_at": now_iso(),
        }
        state["content_genes"].append(gene)
        growth["conclusion"] = decision
        growth["status"] = "learned"
        growth["updated_at"] = now_iso()
        _audit(state, "learning_cycle_completed", cycle["cycle_id"], f"真实结果已回写增长任务 {best_growth_id}：{decision}")
        _save(state)
        return {"cycle": cycle, "content_gene": gene}


def context_export():
    with _LOCK:
        state = _state()
        return {
            "generated_at": now_iso(),
            "policy": state["delivery"]["truth_policy"],
            "counts": dashboard()["counts"],
            "open_growth_cases": [row for row in state["growth_cases"] if row.get("status") not in {"learned", "closed"}][-20:],
            "pending_content_reviews": [row for row in state["content_jobs"] if row.get("approval_state") == "pending"][-20:],
            "pending_publish": [row for row in state["publish_jobs"] if row.get("status") in {"queued", "submitted_waiting_confirmation"}][-20:],
            "human_required": [row for row in state["conversations"] if row.get("state") == "human_required"][-20:],
            "recent_learning": state["learning_cycles"][-10:],
        }


def diagnostics():
    summary = dashboard()
    checks = [
        {"id": "storage", "name": "R8 持久化数据", "status": "pass", "detail": STATE_PATH},
        {"id": "safety", "name": "安全与资金边界", "status": "pass", "detail": "验证码/人脸/资金/风控绕过均不在允许动作中"},
        {"id": "device", "name": "真实 Android 设备", "status": "pass" if summary["devices"]["connected"] else "pending", "detail": f"在线 {summary['devices']['connected']} 台"},
        {"id": "account", "name": "真实平台账号", "status": "pass" if summary["accounts"]["authorized"] else "pending", "detail": f"已授权 {summary['accounts']['authorized']} 个"},
        {"id": "video_worker", "name": "RTX 3060 视频 Worker", "status": "pass" if summary["video_worker"].get("configured") and summary["video_worker"]["hardware"].get("detected") else "pending", "detail": summary["video_worker"]["hardware"].get("name") or "未检测到/未配置"},
        {"id": "receipt", "name": "真实发布回执", "status": "pass" if any(gate["id"] == "Gate 5" and gate["live"] == "ready" for gate in summary["gates"]) else "pending", "detail": "未拿到真实 URL 时不会标记发布成功"},
        {"id": "attribution", "name": "真实归因与学习", "status": "pass" if summary["counts"]["learning_cycles"] else "pending", "detail": "等待首次上线 24h/72h/7天数据"},
    ]
    return {"checks": checks, "summary": summary, "status": "ready_for_live_acceptance"}
