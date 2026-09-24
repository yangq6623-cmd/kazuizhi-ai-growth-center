"""R8-12 truthful publication planner over durable Account Assets.

Legacy ``content_factory.accounts`` is no longer the routing source of truth.
Owner-approved content is routed through the permanent Account Registry, where
account identity, authorization and device health are independent assets.

This module creates plans and may enqueue a Douyin real-device dry-run.  It does
not click a platform's final publish control and never marks content published.
A successful publication still requires a real platform Content/Post ID + URL
receipt.
"""
from __future__ import annotations

from collections import defaultdict

from core.storage import now_iso
from integrations import publish_dry_run_queue
from integrations.account_router import normalize_platform, route_account
from promotion import content_factory

ACTIVE_PLAN_STATES = {"等待最佳时间", "发布执行中", "已验证发布"}
PLATFORM_NAME = {
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "wechat_channels": "视频号",
    "weibo": "微博",
    "bilibili": "B站",
}


def _targets(video):
    requested = list(video.get("target_platforms") or ((video.get("production_plan") or {}).get("target_platforms") or []))
    requested = [str(x or "").strip() for x in requested if str(x or "").strip()]
    # Universal content does not mean "no route".  Use every durable platform
    # currently present in the Account Registry.
    if not requested or "通用" in requested:
        try:
            from core.account_registry import snapshot as account_snapshot
            requested = []
            for account in account_snapshot().get("accounts", []):
                code = normalize_platform(account.get("platform"))
                if code and code not in requested:
                    requested.append(code)
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
            requested = []
    normalized = []
    for item in requested:
        code = normalize_platform(item)
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def _existing_by_platform(plans, video_id):
    mapping = defaultdict(list)
    for plan in plans:
        if plan.get("video_id") != video_id or plan.get("status") not in ACTIVE_PLAN_STATES:
            continue
        code = normalize_platform(plan.get("platform_code") or plan.get("platform"))
        mapping[code].append(plan)
    return mapping


def _publish_fields(video, campaign, platform_code):
    production = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else {}
    adaptation_map = production.get("platform_adaptation") if isinstance(production.get("platform_adaptation"), dict) else {}
    platform_name = PLATFORM_NAME.get(platform_code, platform_code)
    adaptation = adaptation_map.get(platform_name) or adaptation_map.get(platform_code) or adaptation_map.get("通用") or {}
    if not isinstance(adaptation, dict):
        adaptation = {}
    titles = production.get("titles") if isinstance(production.get("titles"), list) else []
    title = str(
        adaptation.get("title")
        or (titles[0] if titles else "")
        or production.get("topic")
        or campaign.get("title")
        or f"{campaign.get('region') or '本地'}{campaign.get('service') or '服务'}"
    ).strip()[:50]
    caption = str(
        adaptation.get("caption")
        or video.get("caption_direction")
        or video.get("cta")
        or campaign.get("goal")
        or title
    ).strip()[:900]
    scheduled_for = str(
        adaptation.get("schedule_hint")
        or "真实执行通道就绪后由系统按账号健康与平台规则编排"
    ).strip()[:60]
    return {"title": title, "caption": caption, "scheduled_for": scheduled_for}


def _create_durable_plan(data: dict, video: dict, campaign: dict, platform_code: str, route: dict, fields: dict) -> dict:
    """Create one plan from a stable account route without legacy re-binding."""
    if not video.get("approved_at") or (video.get("review") or {}).get("decision") != "确认发布":
        raise ValueError("只有老板确认发布的成片才能进入发布编排")
    if not content_factory._claims_safe(fields.get("title"), fields.get("caption")):
        raise ValueError("平台文案包含需要重新审核的绝对化宣传承诺")
    account = route.get("account") or {}
    account_id = str(route.get("account_id") or account.get("account_id") or "").strip()
    if not account_id:
        raise ValueError("缺少永久账号ID")
    plan = {
        "id": content_factory._id("PLAN"),
        "video_id": video["id"],
        "campaign_id": video["campaign_id"],
        "account_id": account_id,
        "account_asset_id": account_id,
        "platform": PLATFORM_NAME.get(platform_code, platform_code),
        "platform_code": platform_code,
        "title": fields["title"],
        "caption": fields["caption"],
        "scheduled_for": fields["scheduled_for"],
        "status": "等待最佳时间",
        "created_at": now_iso(),
        "route_kind": route.get("route_kind"),
        "device_asset_id": route.get("device_id"),
        "execution_source": (
            "官方API待真实执行" if route.get("route_kind") == "official_api"
            else "真实设备待干跑/执行"
        ),
        "truth_rule": "发布计划不是发布结果；只有真实 Content/Post ID + URL / Receipt 才能计为已发布。",
    }
    data.setdefault("publication_plans", []).insert(0, plan)
    return plan


def _queue_device_plan(plan, route, video):
    try:
        return publish_dry_run_queue.queue_plan(plan, route, video)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        return {"queued": False, "reason": str(error)[:300], "publishes_content": False}


def _blocker_text(route: dict, platform_code: str) -> str:
    label = PLATFORM_NAME.get(platform_code, platform_code)
    status = route.get("status")
    if status == "needs_authorization":
        return f"{label}：永久账号存在，但需要重新授权"
    if status == "device_offline":
        return f"{label}：账号已连接，但执行设备离线且当前没有已批准的官方发布API路径"
    if status == "platform_limited":
        return f"{label}：平台能力/审批限制，需要人工处理"
    return f"{label}：没有覆盖当前区域/服务的永久账号资产"


def run_publish_planning(limit=10):
    """Route owner-approved content through durable account assets.

    The function is idempotent per video/platform.  Repeated scheduler ticks do
    not create duplicate publication plans or duplicate device dry-runs.
    """
    data = content_factory._load()
    campaigns = {x.get("id"): x for x in data.get("campaigns", [])}
    videos = [
        x for x in data.get("videos", [])
        if x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布"
        and x.get("status") not in {"已验证发布", "已暂缓"}
    ]
    processed = []

    for video in videos[:max(1, int(limit or 10))]:
        campaign = campaigns.get(video.get("campaign_id"))
        if not campaign:
            continue
        current = content_factory._load()
        latest_video = content_factory._by_id(current.get("videos", []), video["id"], "视频任务")
        existing = _existing_by_platform(current.get("publication_plans", []), video.get("id"))
        targets = _targets(latest_video)
        if not targets:
            latest_video["status"] = "等待账号"
            latest_video["bottleneck"] = "当前没有可路由的平台账号资产"
            latest_video["auto_action"] = "保留老板已审核成片；添加或恢复永久账号资产后自动继续"
            content_factory._save(current)
            processed.append({"video_id": video["id"], "created": 0, "waiting": ["未添加平台账号资产"]})
            continue

        created = []
        waiting = []
        errors = []
        dry_runs = []
        covered = []

        for platform_code in targets:
            route = route_account(
                platform=platform_code,
                region=str(campaign.get("region") or ""),
                service=str(campaign.get("service") or ""),
                require_publish=True,
            )
            existing_plans = existing.get(platform_code) or []
            if route.get("status") != "ready":
                waiting.append(_blocker_text(route, platform_code))
                continue

            if existing_plans:
                plan = existing_plans[0]
                covered.append(platform_code)
                if platform_code == "douyin" and plan.get("route_kind") == "real_device":
                    result = _queue_device_plan(plan, route, latest_video)
                    dry_runs.append(result)
                continue

            try:
                fields = _publish_fields(latest_video, campaign, platform_code)
                plan = _create_durable_plan(current, latest_video, campaign, platform_code, route, fields)
                created.append({
                    "plan_id": plan.get("id"),
                    "platform": PLATFORM_NAME.get(platform_code, platform_code),
                    "platform_code": platform_code,
                    "account_id": plan.get("account_id"),
                    "route_kind": plan.get("route_kind"),
                    "device_asset_id": plan.get("device_asset_id"),
                })
                covered.append(platform_code)
                if platform_code == "douyin" and route.get("route_kind") == "real_device":
                    result = _queue_device_plan(plan, route, latest_video)
                    dry_runs.append(result)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                errors.append(f"{PLATFORM_NAME.get(platform_code, platform_code)}：{str(error)[:300]}")

        missing = [x for x in targets if x not in covered]
        douyin_queue = next((x for x in reversed(dry_runs) if isinstance(x, dict)), None)
        if covered:
            latest_video["status"] = "等待最佳时间"
            latest_video["bottleneck"] = ("尚有平台等待：" + "、".join(PLATFORM_NAME.get(x, x) for x in missing)) if missing else None
            if douyin_queue and douyin_queue.get("queued"):
                latest_video["auto_action"] = "已按永久账号资产建立发布计划并排入抖音真机干跑；最终发布动作仍需真实安全闸门"
            elif any((x.get("route_kind") == "official_api") for x in created):
                latest_video["auto_action"] = "已建立官方API发布计划；必须等待真实平台执行器返回 Content/Post ID + URL"
            else:
                latest_video["auto_action"] = "已建立发布计划；等待真实执行通道并回收真实平台回执"
        else:
            latest_video["status"] = "等待账号"
            latest_video["bottleneck"] = "；".join(waiting[:6]) or "当前没有可执行的永久账号资产"
            latest_video["auto_action"] = "永久账号资产保留；授权或设备恢复后自动重试，不重新绑定 Mission"

        latest_video["publish_planning"] = {
            "targets": targets,
            "covered": covered,
            "missing": missing,
            "last_created": created,
            "last_errors": errors[-10:],
            "douyin_dry_run": douyin_queue,
            "routing_source": "r8_12_durable_account_registry",
            "truth_rule": "发布计划或真机干跑不等于发布；只有真实 Content/Post ID + URL / Receipt 才能标记已验证发布。",
            "updated_at": now_iso(),
        }
        content_factory._save(current)
        processed.append({
            "video_id": video["id"],
            "created": len(created),
            "created_plans": created,
            "covered": covered,
            "waiting": waiting,
            "errors": errors,
            "dry_runs": dry_runs,
        })

    return {
        "processed": len(processed),
        "items": processed,
        "routing_source": "r8_12_durable_account_registry",
        "truth_rule": "没有真实平台 Receipt，不计为已发布。",
    }
