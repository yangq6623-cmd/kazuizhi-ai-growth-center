"""R8-12 truthful publication planner over durable Account Assets.

Publication planning is independent from device liveness: once a durable account
identity is authorized, the owner-approved video may receive an idempotent plan.
Execution waits for an approved official API path or an online Device Asset.
Neither a plan nor a dry-run is publication success; only a real Content/Post ID
+ URL / Receipt can close the loop.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from core.storage import now_iso
from integrations import publish_dry_run_queue
from integrations.account_router import normalize_platform, route_account
from promotion import content_factory, platform_rules

ACTIVE_PLAN_STATES = {"等待最佳时间", "等待执行设备", "发布执行中", "已验证发布"}
PLATFORM_NAME = {
    "douyin": "抖音", "kuaishou": "快手", "xiaohongshu": "小红书",
    "wechat_channels": "视频号", "weibo": "微博", "bilibili": "B站",
}


def _targets(video):
    requested = list(video.get("target_platforms") or ((video.get("production_plan") or {}).get("target_platforms") or []))
    requested = [str(x or "").strip() for x in requested if str(x or "").strip()]
    if not requested or "通用" in requested:
        try:
            from core.account_registry import snapshot as account_snapshot
            requested = []
            for account in account_snapshot().get("accounts", []):
                code = normalize_platform(account.get("platform"))
                if code and code not in requested: requested.append(code)
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
            requested = []
    normalized = []
    for item in requested:
        code = normalize_platform(item)
        if code and code not in normalized: normalized.append(code)
    return normalized


def _existing_by_platform(plans, video_id):
    mapping = defaultdict(list)
    for plan in plans:
        if plan.get("video_id") != video_id or plan.get("status") not in ACTIVE_PLAN_STATES: continue
        mapping[normalize_platform(plan.get("platform_code") or plan.get("platform"))].append(plan)
    return mapping


def _publish_fields(video, campaign, platform_code):
    production = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else {}
    adaptation_map = production.get("platform_adaptation") if isinstance(production.get("platform_adaptation"), dict) else {}
    platform_name = PLATFORM_NAME.get(platform_code, platform_code)
    adaptation = adaptation_map.get(platform_name) or adaptation_map.get(platform_code) or adaptation_map.get("通用") or {}
    if not isinstance(adaptation, dict): adaptation = {}
    suggested = platform_rules.suggested_publish_fields(video, platform_name)
    titles = production.get("titles") if isinstance(production.get("titles"), list) else []
    title = str(adaptation.get("title") or suggested.get("title") or (titles[0] if titles else "") or production.get("topic") or campaign.get("title") or f"{campaign.get('region') or '本地'}{campaign.get('service') or '服务'}").strip()[:50]
    caption = str(adaptation.get("caption") or suggested.get("caption") or video.get("caption_direction") or video.get("cta") or campaign.get("goal") or title).strip()[:900]
    scheduled_for = str(adaptation.get("schedule_hint") or suggested.get("scheduled_for") or "真实执行通道就绪后由系统按账号健康与平台规则编排").strip()[:60]
    return {"title": title, "caption": caption, "scheduled_for": scheduled_for, "suggested": suggested}


def _daily_cap(data, account_id, platform_name):
    internal = platform_rules.INTERNAL_CAPS.get(platform_name, platform_rules.INTERNAL_CAPS.get("通用", {"daily_publish": 1}))
    cap = max(1, int(internal.get("daily_publish") or 1))
    today = datetime.now().astimezone().date().isoformat()
    used = sum(1 for plan in data.get("publication_plans", []) if plan.get("account_id") == account_id and str(plan.get("created_at") or "")[:10] == today and plan.get("status") in ACTIVE_PLAN_STATES)
    if used >= cap:
        raise ValueError(f"发布前硬规则未通过：该账号今天已达到内部发布上限 {cap} 条")
    return {"limit": cap, "used_before_this_plan": used, "date": today}


def _create_durable_plan(data, video, campaign, platform_code, route, fields):
    if not video.get("approved_at") or (video.get("review") or {}).get("decision") != "确认发布":
        raise ValueError("只有老板确认发布的成片才能进入发布编排")
    account = route.get("account") or {}; account_id = str(route.get("account_id") or account.get("account_id") or "").strip()
    if not account_id: raise ValueError("缺少永久账号ID")
    platform_name = PLATFORM_NAME.get(platform_code, platform_code)
    # R8-12 source of truth is the durable router, not the retired content-factory
    # account row. A ready/device_offline route can only be returned for an
    # authorized durable account. Feed that verified truth into the immutable
    # platform safety rules without re-binding the account to a Mission/device.
    rule_account = {
        "id": account_id,
        "platform": platform_name,
        "daily_limit": 1,
        "connection_status": "已验证可发布" if route.get("status") in {"ready", "device_offline"} else "待人工登录授权",
        "verification_source": "r8_12_durable_account_registry",
    }
    rule_check = platform_rules.evaluate(video, rule_account, fields["title"], fields["caption"])
    if not rule_check.get("passed"):
        raise ValueError("发布前硬规则未通过：" + "；".join(rule_check.get("hard_issues") or ["平台规则不通过"]))
    if not content_factory._claims_safe(fields.get("title"), fields.get("caption")):
        raise ValueError("平台文案包含需要重新审核的绝对化宣传承诺")
    daily_cap = _daily_cap(data, account_id, platform_name)
    executable = route.get("status") == "ready"
    plan = {
        "id": content_factory._id("PLAN"), "video_id": video["id"], "campaign_id": video["campaign_id"],
        "account_id": account_id, "account_asset_id": account_id, "platform": platform_name, "platform_code": platform_code,
        "title": fields["title"], "caption": fields["caption"], "scheduled_for": fields["scheduled_for"],
        "status": "等待最佳时间" if executable else "等待执行设备", "created_at": now_iso(),
        "route_kind": route.get("route_kind"), "device_asset_id": route.get("device_id"),
        "execution_source": "官方API待真实执行" if route.get("route_kind") == "official_api" else ("真实设备待干跑/执行" if executable else "账号已规划，等待真实执行设备"),
        "rule_check": rule_check,
        "strategy_source": (fields.get("suggested") or {}).get("source") or "chatgpt_platform_adaptation",
        "platform_adaptation": fields.get("suggested") or {},
        "daily_cap": daily_cap,
        "truth_rule": "发布计划不是发布结果；只有真实 Content/Post ID + URL / Receipt 才能计为已发布。",
    }
    data.setdefault("publication_plans", []).insert(0, plan)
    return plan


def _queue_device_plan(plan, route, video):
    try: return publish_dry_run_queue.queue_plan(plan, route, video)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        return {"queued": False, "reason": str(error)[:300], "publishes_content": False}


def _blocker_text(route, platform_code):
    label, status = PLATFORM_NAME.get(platform_code, platform_code), route.get("status")
    if status == "needs_authorization": return f"{label}：永久账号存在，但需要重新授权"
    if status == "device_offline": return f"{label}：账号已连接，发布计划可保留；等待执行设备上线或获批官方发布API"
    if status == "platform_limited": return f"{label}：平台能力/审批限制，需要人工处理"
    return f"{label}：没有覆盖当前区域/服务的永久账号资产"


def run_publish_planning(limit=10):
    data = content_factory._load(); campaigns = {x.get("id"): x for x in data.get("campaigns", [])}
    videos = [x for x in data.get("videos", []) if x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布" and x.get("status") not in {"已验证发布", "已暂缓"}]
    processed = []
    for video in videos[:max(1, int(limit or 10))]:
        campaign = campaigns.get(video.get("campaign_id"))
        if not campaign: continue
        current = content_factory._load(); latest_video = content_factory._by_id(current.get("videos", []), video["id"], "视频任务")
        existing = _existing_by_platform(current.get("publication_plans", []), video.get("id")); targets = _targets(latest_video)
        if not targets:
            latest_video.update({"status": "等待账号", "bottleneck": "当前没有可路由的平台账号资产", "auto_action": "保留老板已审核成片；添加或恢复永久账号资产后自动继续"})
            content_factory._save(current); processed.append({"video_id": video["id"], "created": 0, "waiting": ["未添加平台账号资产"]}); continue

        created, waiting, errors, dry_runs, covered = [], [], [], [], []
        for platform_code in targets:
            route = route_account(platform=platform_code, region=str(campaign.get("region") or ""), service=str(campaign.get("service") or ""), require_publish=True)
            existing_plans = existing.get(platform_code) or []
            if existing_plans:
                plan = existing_plans[0]; covered.append(platform_code)
                if route.get("status") == "ready" and plan.get("status") == "等待执行设备":
                    plan["status"] = "等待最佳时间"; plan["route_kind"] = route.get("route_kind"); plan["device_asset_id"] = route.get("device_id")
                if platform_code == "douyin" and route.get("status") == "ready" and route.get("route_kind") == "real_device": dry_runs.append(_queue_device_plan(plan, route, latest_video))
                continue

            # Device-offline is an execution blocker, not an identity/planning blocker.
            # We keep one durable plan so reconnecting the device never requires the
            # owner to rebind the account or rebuild the Mission.
            can_plan = route.get("status") in {"ready", "device_offline"} and bool(route.get("account_id"))
            if not can_plan:
                waiting.append(_blocker_text(route, platform_code)); continue
            try:
                fields = _publish_fields(latest_video, campaign, platform_code)
                plan = _create_durable_plan(current, latest_video, campaign, platform_code, route, fields)
                created.append({"plan_id": plan.get("id"), "platform": PLATFORM_NAME.get(platform_code, platform_code), "platform_code": platform_code, "account_id": plan.get("account_id"), "route_kind": plan.get("route_kind"), "device_asset_id": plan.get("device_asset_id")})
                covered.append(platform_code)
                if route.get("status") == "device_offline": waiting.append(_blocker_text(route, platform_code))
                if platform_code == "douyin" and route.get("status") == "ready" and route.get("route_kind") == "real_device": dry_runs.append(_queue_device_plan(plan, route, latest_video))
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                errors.append(f"{PLATFORM_NAME.get(platform_code, platform_code)}：{str(error)[:300]}")

        missing = [x for x in targets if x not in covered]; douyin_queue = next((x for x in reversed(dry_runs) if isinstance(x, dict)), None)
        executable_covered = [x for x in covered if not any(msg.startswith(f"{PLATFORM_NAME.get(x,x)}：账号已连接，发布计划可保留") for msg in waiting)]
        if covered:
            latest_video["status"] = "等待最佳时间" if executable_covered else "等待账号"
            latest_video["bottleneck"] = "；".join(waiting[:6]) or (("尚有平台等待：" + "、".join(PLATFORM_NAME.get(x, x) for x in missing)) if missing else None)
            if douyin_queue and douyin_queue.get("queued"): latest_video["auto_action"] = "已按永久账号资产建立发布计划并排入抖音真机干跑；最终发布动作仍需真实安全闸门"
            elif executable_covered: latest_video["auto_action"] = "已建立可执行发布计划；等待真实平台执行并回收 Content/Post ID + URL"
            else: latest_video["auto_action"] = "发布计划与永久账号已保留；设备上线后自动继续，无需重新绑定"
        else:
            latest_video.update({"status": "等待账号", "bottleneck": "；".join(waiting[:6]) or "当前没有可执行的永久账号资产", "auto_action": "永久账号资产保留；授权或设备恢复后自动重试，不重新绑定 Mission"})

        latest_video["publish_planning"] = {"targets": targets, "covered": covered, "missing": missing, "last_created": created, "last_errors": errors[-10:], "douyin_dry_run": douyin_queue, "routing_source": "r8_12_durable_account_registry", "truth_rule": "发布计划或真机干跑不等于发布；只有真实 Content/Post ID + URL / Receipt 才能标记已验证发布。", "updated_at": now_iso()}
        content_factory._save(current)
        processed.append({"video_id": video["id"], "created": len(created), "created_plans": created, "covered": covered, "waiting": waiting, "errors": errors, "dry_runs": dry_runs})

    return {"processed": len(processed), "items": processed, "routing_source": "r8_12_durable_account_registry", "truth_rule": "没有真实平台 Receipt，不计为已发布。"}
