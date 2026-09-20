"""A truthful content supply line from local signal to verified publication.

This module deliberately separates a proposal, a locally rendered video and a
verified platform publication.  It never posts to social platforms itself.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from core.storage import now_iso, read_json, write_json


FACTORY_FILE = "r8/content_factory.json"
REGIONS = ("涟水县", "清江浦区", "淮安区", "淮阴区")
SERVICES = ("家电安装维修", "水电安装维修", "管道疏通维修", "家政服务", "邻里个人任务")
VIDEO_STATES = (
    "待补充素材", "等待生产", "生产中", "等待人工审核", "退回修改",
    "已授权发布", "等待账号", "等待最佳时间", "发布执行中", "已验证发布", "发布失败",
)
RISKY_TERMS = ("最低价", "全城第一", "保证", "百分百", "100%", "假一赔", "绝对")


def _default():
    return {
        "schema_version": 1,
        "migrated_at": now_iso(),
        "campaigns": [],
        "assets": [],
        "videos": [],
        "accounts": [],
        "publication_plans": [],
        "receipts": [],
        "feedback": [],
    }


def _load():
    data = read_json(FACTORY_FILE, _default())
    if not isinstance(data, dict):
        data = _default()
    for key, value in _default().items():
        data.setdefault(key, value)
    if not data["accounts"]:
        legacy = read_json("r8/control.json", {})
        platform_names = {"douyin": "抖音", "xiaohongshu": "小红书", "kuaishou": "快手", "wechat_channels": "视频号", "weibo": "微博", "bilibili": "B站"}
        for account in legacy.get("accounts", []) if isinstance(legacy, dict) else []:
            platform = account.get("platform") or account.get("platform_id") or "其他"
            legacy_status = account.get("status") or account.get("connection") or ""
            data["accounts"].append({
                "id": str(account.get("account_id") or account.get("id") or _id("ACCOUNT")),
                "platform": platform_names.get(platform, account.get("platform_name") or platform),
                "account_name": str(account.get("label") or account.get("alias") or account.get("account_name") or "旧版已绑定账号"),
                "region": str(account.get("region") or ""), "service": str(account.get("service") or ""),
                "connection_status": "已验证可发布" if legacy_status in {"connected", "logged_in", "ready", "verified"} else "待人工登录授权",
                "device_id": str(account.get("device_id") or ""), "daily_limit": max(1, min(int(account.get("daily_limit") or 1), 3)),
                "preferred_windows": account.get("preferred_windows") or [], "migrated_from": "r8/control.json",
            })
        if data["accounts"]:
            write_json(FACTORY_FILE, data)
    return data


def _save(data):
    return write_json(FACTORY_FILE, data)


def _clean(value, name, limit=200, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{name}不能为空")
    if len(value) > limit:
        raise ValueError(f"{name}长度不能超过{limit}个字符")
    return value


def _id(prefix):
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _by_id(items, identifier, label):
    for item in items:
        if item.get("id") == identifier:
            return item
    raise ValueError(f"未找到{label}")


def _claims_safe(*values):
    text = " ".join(str(value or "") for value in values).lower()
    return not any(term.lower() in text for term in RISKY_TERMS)


def create_campaign(payload):
    """Create one traceable local-content opportunity, not a publication."""
    region = _clean(payload.get("region"), "区域", 40)
    service = _clean(payload.get("service"), "服务项目", 60)
    if region not in REGIONS:
        raise ValueError("区域必须是当前已开放的四个区域之一")
    if service not in SERVICES:
        raise ValueError("服务项目不在当前内容工厂范围内")
    title = _clean(payload.get("title"), "选题", 120)
    evidence = _clean(payload.get("evidence"), "选题依据", 500)
    goal = _clean(payload.get("goal") or "获得可追溯的本地咨询或小程序需求", "业务目标", 160)
    data = _load()
    item = {
        "id": _id("KZ"), "created_at": now_iso(), "region": region,
        "service": service, "title": title, "evidence": evidence, "goal": goal,
        "source_type": _clean(payload.get("source_type") or "本地需求信号", "来源类型", 40),
        "status": "待补充素材", "owner_note": _clean(payload.get("owner_note"), "补充说明", 300, False),
    }
    data["campaigns"].insert(0, item)
    _save(data)
    return item


def add_asset(payload):
    data = _load()
    campaign = _by_id(data["campaigns"], _clean(payload.get("campaign_id"), "增长ID", 64), "增长任务")
    kind = _clean(payload.get("kind"), "素材类型", 30)
    if kind not in ("真实现场视频", "真实现场照片", "师傅讲解", "品牌素材", "AI辅助镜头"):
        raise ValueError("素材类型不合法")
    local_path = _clean(payload.get("local_path"), "本地素材路径", 500)
    exists = Path(local_path).is_file()
    item = {
        "id": _id("ASSET"), "campaign_id": campaign["id"], "created_at": now_iso(),
        "kind": kind, "local_path": local_path, "exists": exists,
        "duration_seconds": payload.get("duration_seconds"),
        "consent_confirmed": bool(payload.get("consent_confirmed")),
        "note": _clean(payload.get("note"), "素材说明", 300, False),
    }
    if kind.startswith("真实") and not item["consent_confirmed"]:
        raise ValueError("真实现场素材必须确认已取得用户拍摄与发布同意")
    data["assets"].insert(0, item)
    campaign["status"] = "可建立视频任务" if exists else "素材路径待确认"
    _save(data)
    return item


def create_video(payload):
    data = _load()
    campaign = _by_id(data["campaigns"], _clean(payload.get("campaign_id"), "增长ID", 64), "增长任务")
    assets = [x for x in data["assets"] if x.get("campaign_id") == campaign["id"] and x.get("exists")]
    if not assets:
        raise ValueError("请先添加至少一个真实存在的本地素材")
    script = _clean(payload.get("script"), "脚本", 2000)
    if not _claims_safe(script, payload.get("caption"), payload.get("cta")):
        raise ValueError("脚本或文案包含需要人工改写的绝对化宣传承诺")
    item = {
        "id": _id("VIDEO"), "campaign_id": campaign["id"], "created_at": now_iso(),
        "script": script, "duration_target": int(payload.get("duration_target") or 18),
        "caption_direction": _clean(payload.get("caption"), "配文方向", 500, False),
        "cta": _clean(payload.get("cta") or "通过小程序提交需求，等待师傅报价", "行动提示", 160),
        "asset_ids": [x["id"] for x in assets], "candidates": [], "status": "等待生产",
        "review": None, "approved_at": None,
    }
    data["videos"].insert(0, item)
    campaign["status"] = "视频生产中"
    _save(data)
    return item


def record_candidate(payload):
    data = _load()
    video = _by_id(data["videos"], _clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    local_path = _clean(payload.get("local_path"), "成片路径", 500)
    candidate = {
        "id": _id("CUT"), "created_at": now_iso(), "local_path": local_path,
        "exists": Path(local_path).is_file(), "duration_seconds": payload.get("duration_seconds"),
        "quality_notes": _clean(payload.get("quality_notes"), "质检说明", 500, False),
        "ai_score": payload.get("ai_score"),
    }
    video["candidates"].append(candidate)
    video["status"] = "等待人工审核" if candidate["exists"] else "生产中"
    _save(data)
    return candidate


def review_video(payload):
    data = _load()
    video = _by_id(data["videos"], _clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    decision = _clean(payload.get("decision"), "审核决定", 30)
    if decision not in ("确认发布", "退回修改", "重做指定镜头", "整片重做"):
        raise ValueError("审核决定不合法")
    if decision == "确认发布":
        candidate_id = _clean(payload.get("candidate_id"), "审核成片", 64)
        candidate = _by_id(video["candidates"], candidate_id, "成片候选")
        if not candidate.get("exists"):
            raise ValueError("成片文件不存在，不能确认发布")
        video["status"] = "已授权发布"
        video["approved_at"] = now_iso()
    else:
        video["status"] = "退回修改"
    video["review"] = {
        "decision": decision, "reviewed_at": now_iso(),
        "note": _clean(payload.get("note"), "审核意见", 500, False),
    }
    _save(data)
    return video


def save_account(payload):
    """Save account routing only. Credentials stay in the platform connector vault."""
    data = _load()
    platform = _clean(payload.get("platform"), "平台", 30)
    account_name = _clean(payload.get("account_name"), "账号名称", 80)
    item = {
        "id": _clean(payload.get("id") or _id("ACCOUNT"), "账号ID", 64),
        "platform": platform, "account_name": account_name,
        "region": _clean(payload.get("region"), "区域", 40, False),
        "service": _clean(payload.get("service"), "服务主线", 60, False),
        "connection_status": _clean(payload.get("connection_status") or "待人工登录授权", "连接状态", 40),
        "device_id": _clean(payload.get("device_id"), "设备ID", 120, False),
        "daily_limit": max(1, min(int(payload.get("daily_limit") or 1), 3)),
        "preferred_windows": payload.get("preferred_windows") or [],
    }
    existing = next((x for x in data["accounts"] if x.get("id") == item["id"]), None)
    if existing:
        existing.update(item)
    else:
        data["accounts"].append(item)
    _save(data)
    return item


def create_publish_plan(payload):
    data = _load()
    video = _by_id(data["videos"], _clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    if video.get("status") != "已授权发布":
        raise ValueError("只有人工确认发布的视频才能进入发布编排")
    account = _by_id(data["accounts"], _clean(payload.get("account_id"), "账号ID", 64), "账号")
    if account.get("connection_status") != "已验证可发布":
        video["status"] = "等待账号"
        _save(data)
        raise ValueError("账号尚未完成真实登录授权或可发布验证")
    title = _clean(payload.get("title"), "平台标题", 100)
    caption = _clean(payload.get("caption"), "平台配文", 1000)
    if not _claims_safe(title, caption):
        raise ValueError("平台文案包含需要重新审核的绝对化宣传承诺")
    plan = {
        "id": _id("PLAN"), "video_id": video["id"], "campaign_id": video["campaign_id"],
        "account_id": account["id"], "platform": account["platform"], "title": title,
        "caption": caption, "scheduled_for": _clean(payload.get("scheduled_for"), "建议发布时间", 60),
        "status": "等待最佳时间", "created_at": now_iso(), "execution_source": "待连接器或真机执行",
    }
    data["publication_plans"].insert(0, plan)
    video["status"] = "等待最佳时间"
    _save(data)
    return plan


def record_receipt(payload):
    data = _load()
    plan = _by_id(data["publication_plans"], _clean(payload.get("plan_id"), "发布计划ID", 64), "发布计划")
    result = _clean(payload.get("result"), "执行结果", 30)
    if result not in ("成功", "失败", "需要人工处理"):
        raise ValueError("执行结果不合法")
    receipt = {
        "id": _id("RECEIPT"), "plan_id": plan["id"], "created_at": now_iso(), "result": result,
        "platform_content_id": _clean(payload.get("platform_content_id"), "平台内容ID", 160, result == "成功"),
        "url": _clean(payload.get("url"), "真实内容链接", 500, result == "成功"),
        "reason": _clean(payload.get("reason"), "执行说明", 500, False),
    }
    if result == "成功" and not re.match(r"https?://", receipt["url"], re.I):
        raise ValueError("成功回执必须提供真实的 http 或 https 内容链接")
    plan["status"] = "已验证发布" if result == "成功" else "发布失败"
    video = _by_id(data["videos"], plan["video_id"], "视频任务")
    video["status"] = plan["status"]
    data["receipts"].insert(0, receipt)
    _save(data)
    return receipt


def dashboard():
    data = _load()
    counts = {state: sum(1 for x in data["videos"] if x.get("status") == state) for state in VIDEO_STATES}
    verified = {x.get("plan_id") for x in data["receipts"] if x.get("result") == "成功"}
    return {
        "status": "available", "truth_rule": "只有本地成片存在、人工审核、账号验证和真实平台回执全部完成，才显示为已发布。",
        "regions": list(REGIONS), "services": list(SERVICES), "video_states": counts,
        "campaigns": data["campaigns"][:30], "assets": data["assets"][:50], "videos": data["videos"][:30],
        "accounts": data["accounts"], "publication_plans": data["publication_plans"][:50],
        "receipts": data["receipts"][:50], "verified_publications": len(verified),
    }
