"""Automatic publication planning after the owner's final approval.

This module never logs into an account and never claims a platform publication.
It only converts an already owner-approved FINAL.MP4 plus ChatGPT platform
adaptation into safe per-platform plans for accounts that have already been
verified by the local control plane. Real execution still requires the existing
connector/real-device path and a real receipt.
"""

from __future__ import annotations

from collections import defaultdict

from promotion import content_factory


ACTIVE_PLAN_STATES = {"等待最佳时间", "发布执行中", "已验证发布"}


def _targets(video, accounts):
    requested = list(video.get("target_platforms") or ((video.get("production_plan") or {}).get("target_platforms") or []))
    requested = [str(x or "").strip() for x in requested if str(x or "").strip()]
    if not requested or "通用" in requested:
        requested = []
        for account in accounts:
            platform = str(account.get("platform") or "").strip()
            if platform and platform not in requested:
                requested.append(platform)
    return requested


def _matching_accounts(accounts, campaign, platform):
    candidates = []
    for account in accounts:
        if account.get("connection_status") != "已验证可发布":
            continue
        if str(account.get("platform") or "") != platform:
            continue
        region = str(account.get("region") or "").strip()
        service = str(account.get("service") or "").strip()
        if region and region != str(campaign.get("region") or ""):
            continue
        if service and service != str(campaign.get("service") or ""):
            continue
        candidates.append(account)
    # Prefer the account with the largest configured daily allowance. The hard
    # rule layer still checks the actual remaining allowance atomically.
    candidates.sort(key=lambda x: int(x.get("daily_limit") or 1), reverse=True)
    return candidates


def _existing_by_platform(plans, video_id):
    mapping = defaultdict(list)
    for plan in plans:
        if plan.get("video_id") != video_id or plan.get("status") not in ACTIVE_PLAN_STATES:
            continue
        mapping[str(plan.get("platform") or "")].append(plan)
    return mapping


def run_publish_planning(limit=10):
    """Create missing per-platform plans for approved videos.

    The function is idempotent. Account/login gaps are surfaced as bottlenecks
    but do not invalidate an already-created plan for another platform.
    """
    data = content_factory._load()
    campaigns = {x.get("id"): x for x in data.get("campaigns", [])}
    accounts = list(data.get("accounts", []))
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
        existing = _existing_by_platform(current.get("publication_plans", []), video.get("id"))
        targets = _targets(video, accounts)
        if not targets:
            content_factory.update_runtime_state(
                video["id"], status="等待账号",
                bottleneck="没有可用于发布编排的平台账号",
                auto_action="保留已审核成片；检测到已验证账号后自动继续编排",
            )
            processed.append({"video_id": video["id"], "created": 0, "waiting": ["未配置平台账号"]})
            continue

        created = []
        waiting = []
        errors = []
        for platform in targets:
            if existing.get(platform):
                continue
            candidates = _matching_accounts(accounts, campaign, platform)
            if not candidates:
                waiting.append(f"{platform}：缺少区域/服务匹配且已验证可发布的账号")
                continue
            planned = None
            for account in candidates:
                try:
                    planned = content_factory.create_publish_plan({
                        "video_id": video["id"],
                        "account_id": account["id"],
                    })
                    created.append({
                        "plan_id": planned.get("id"), "platform": platform,
                        "account_id": account.get("id"),
                    })
                    break
                except ValueError as error:
                    errors.append(f"{platform}/{account.get('account_name')}: {error}")
            if planned is None and not any(x.startswith(platform + "：") for x in waiting):
                waiting.append(f"{platform}：当前账号达到上限或未通过发布硬规则")

        latest = content_factory._load()
        latest_video = content_factory._by_id(latest.get("videos", []), video["id"], "视频任务")
        plans_now = _existing_by_platform(latest.get("publication_plans", []), video["id"])
        covered = [platform for platform in targets if plans_now.get(platform)]
        missing = [platform for platform in targets if platform not in covered]
        if covered:
            latest_video["status"] = "等待最佳时间"
            latest_video["bottleneck"] = ("尚有平台等待账号：" + "、".join(missing)) if missing else None
            latest_video["auto_action"] = (
                "已按ChatGPT平台策略自动建立发布计划；真实连接器/真机执行后必须回收平台内容ID和URL"
                if not missing else
                "已完成可用平台编排；缺少账号的平台会在账号验证后自动补齐"
            )
        else:
            latest_video["status"] = "等待账号"
            latest_video["bottleneck"] = "；".join(waiting[:6]) or "当前没有可执行的已验证账号"
            latest_video["auto_action"] = "保留最终成片与审核结果；账号完成真实登录验证后自动重试编排"
        latest_video["publish_planning"] = {
            "targets": targets,
            "covered": covered,
            "missing": missing,
            "last_created": created,
            "last_errors": errors[-10:],
        }
        content_factory._save(latest)
        processed.append({
            "video_id": video["id"], "created": len(created), "created_plans": created,
            "covered": covered, "waiting": waiting, "errors": errors,
        })
    return {"processed": len(processed), "items": processed}
