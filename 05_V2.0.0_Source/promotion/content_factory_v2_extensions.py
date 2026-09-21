"""Completion layer for the R8 ChatGPT-controlled content factory.

The base R8 supply chain remains backward compatible.  This extension adds the
remaining production semantics without introducing another planning model:
structured asset metadata, ChatGPT post-render QC, review-aware replanning,
platform hard-rule checks, production audit events and feedback learning.
"""

from __future__ import annotations

from pathlib import Path

from core.storage import now_iso
from promotion import content_factory as cf
from promotion import platform_rules


_INSTALLED = False
_ORIGINAL = {}


def _event(data, kind, *, video_id=None, campaign_id=None, detail=None):
    events = data.setdefault("events", [])
    events.append({
        "id": cf._id("EVT"),
        "created_at": now_iso(),
        "kind": str(kind or "event")[:80],
        "video_id": video_id,
        "campaign_id": campaign_id,
        "detail": detail if isinstance(detail, dict) else {"message": str(detail or "")[:500]},
    })
    data["events"] = events[-1000:]


def _enhanced_normalize_contract(payload, campaign=None):
    plan = _ORIGINAL["normalize_contract"](payload, campaign)
    raw = payload if isinstance(payload, dict) else {}
    mapping = raw.get("platform_adaptation") if isinstance(raw.get("platform_adaptation"), dict) else {}
    normalized = {}
    for platform in plan.get("target_platforms") or ["通用"]:
        source = mapping.get(platform) or mapping.get("通用") or {}
        if not isinstance(source, dict):
            source = {}
        title = str(source.get("title") or (plan.get("titles") or [plan.get("topic")])[0])[:120].strip()
        caption = str(source.get("caption") or "")[:1000].strip()
        normalized[platform] = {
            "hook": str(source.get("hook") or "")[:160].strip(),
            "title": title,
            "caption": caption,
            "cover_title": str(source.get("cover_title") or plan.get("cover", {}).get("title") or title)[:120].strip(),
            "pacing": str(source.get("pacing") or "")[:160].strip(),
            "schedule_hint": str(source.get("schedule_hint") or "由ChatGPT结合账号状态与真实历史效果选择")[:160].strip(),
            "cta": str(source.get("cta") or plan.get("cta") or "")[:160].strip(),
        }
    plan["platform_adaptation"] = normalized
    plan["rule_center"] = {
        "hard_rules_fixed": True,
        "strategy_owner": "ChatGPT",
        "rule_schema": "kazuizhi-platform-rule-center/v1",
    }
    return plan


def add_asset(payload):
    item = _ORIGINAL["add_asset"](payload)
    extras = {
        "source_origin": str(payload.get("source_origin") or "manual_upload")[:80],
        "source_fingerprint": str(payload.get("source_fingerprint") or "")[:128],
        "license": payload.get("license") if isinstance(payload.get("license"), dict) else {},
        "media_metadata": payload.get("media_metadata") if isinstance(payload.get("media_metadata"), dict) else {},
        "indexed_at": now_iso(),
    }
    data = cf._load()
    asset = cf._by_id(data.get("assets", []), item["id"], "素材")
    asset.update(extras)
    _event(data, "asset_indexed", campaign_id=asset.get("campaign_id"), detail={
        "asset_id": asset.get("id"), "kind": asset.get("kind"), "origin": asset.get("source_origin"),
    })
    cf._save(data)
    return asset


def pending_chatgpt_handoff(limit=20):
    data = cf._load()
    requests = []
    for video in data.get("videos", []):
        if video.get("status") not in {"等待ChatGPT策划", "退回重做"}:
            continue
        campaign = next((x for x in data.get("campaigns", []) if x.get("id") == video.get("campaign_id")), None)
        if not campaign:
            continue
        assets = [
            x for x in data.get("assets", [])
            if x.get("campaign_id") == campaign["id"] and x.get("exists")
        ]
        previous = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else None
        requests.append({
            "video_id": video["id"],
            "campaign_id": campaign["id"],
            "region": campaign.get("region"),
            "service": campaign.get("service"),
            "growth_goal": campaign.get("goal"),
            "user_problem": campaign.get("title"),
            "evidence": campaign.get("evidence"),
            "available_assets": [
                {
                    "asset_id": x.get("id"), "kind": x.get("kind"), "tags": x.get("tags") or [],
                    "origin": x.get("source_origin") or "manual_upload",
                    "quality_score": x.get("quality_score"),
                    "license": x.get("license") or {},
                    "media_metadata": x.get("media_metadata") or {},
                }
                for x in assets[:40]
            ],
            "local_material_optional": True,
            "owner_review": video.get("review"),
            "previous_chatgpt_qc": video.get("chatgpt_qc"),
            "previous_plan_version": video.get("plan_version") or 0,
            "previous_plan": previous,
            "platform_rule_center": platform_rules.snapshot(),
            "instruction": (
                "ChatGPT是唯一总控制。请结合增长目标、真实反馈、素材索引和平台硬规则生成或重做选题、痛点、"
                "标题、深层脚本、分镜、素材来源优先级、平台适配和质检标准。不要机械重复被退回版本。"
                "按kazuizhi-content-production/v1返回kind=content_production。"
            ),
        })
        if len(requests) >= max(1, int(limit or 20)):
            break
    return {"schema": "kazuizhi-content-production-requests/v2", "items": requests, "count": len(requests)}


def pending_chatgpt_qc_handoff(limit=20):
    data = cf._load()
    requests = []
    for video in data.get("videos", []):
        if video.get("status") != "等待ChatGPT质检":
            continue
        candidate = next((x for x in reversed(video.get("candidates") or []) if x.get("exists")), None)
        if not candidate:
            continue
        path = Path(str(candidate.get("local_path") or ""))
        requests.append({
            "video_id": video.get("id"),
            "campaign_id": video.get("campaign_id"),
            "candidate_id": candidate.get("id"),
            "plan_version": video.get("plan_version") or 0,
            "target_platforms": video.get("target_platforms") or [],
            "technical_qc": candidate.get("technical_qc") or video.get("technical_qc"),
            "source_summary": candidate.get("source_summary") or [],
            "production_plan": video.get("production_plan"),
            "local_candidate_path": str(path) if path.is_file() else None,
            "file_bytes": path.stat().st_size if path.is_file() else None,
            "criteria": ((video.get("production_plan") or {}).get("qc") or {}).get("chatgpt") or [
                "goal_alignment", "truthfulness", "script_storyboard_match", "platform_fit"
            ],
            "instruction": (
                "请由ChatGPT执行内容质检，判断经营目标一致性、真实性、脚本与画面一致性、平台适配和表达质量。"
                "通过则返回kind=content_qc, decision=pass；需要修改则返回decision=rework，并给reasons和shot_feedback。"
            ),
        })
        if len(requests) >= max(1, int(limit or 20)):
            break
    return {"schema": "kazuizhi-content-qc-requests/v1", "items": requests, "count": len(requests)}


def apply_chatgpt_qc(payload):
    if not isinstance(payload, dict):
        raise ValueError("ChatGPT质检结果格式不正确")
    data = cf._load()
    video = cf._by_id(data.get("videos", []), cf._clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    candidate = cf._by_id(video.get("candidates", []), cf._clean(payload.get("candidate_id"), "成片候选", 64), "成片候选")
    if not candidate.get("exists") or not Path(str(candidate.get("local_path") or "")).is_file():
        raise ValueError("ChatGPT质检对应的成片文件不存在")
    if not (candidate.get("technical_qc") or {}).get("passed"):
        raise ValueError("技术质检未通过，不能进入ChatGPT内容质检")
    decision = str(payload.get("decision") or "").strip().lower()
    aliases = {"通过": "pass", "pass": "pass", "rework": "rework", "重做": "rework", "修改": "rework"}
    decision = aliases.get(decision, decision)
    if decision not in {"pass", "rework"}:
        raise ValueError("ChatGPT质检decision必须为pass或rework")
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    shot_feedback = payload.get("shot_feedback") if isinstance(payload.get("shot_feedback"), list) else []
    try:
        score = float(payload.get("score")) if payload.get("score") not in (None, "") else None
    except (TypeError, ValueError):
        score = None
    result = {
        "status": "passed" if decision == "pass" else "rework",
        "decision": decision,
        "score": score,
        "reasons": [str(x)[:300] for x in reasons[:20]],
        "shot_feedback": [x for x in shot_feedback[:30] if isinstance(x, dict)],
        "reviewed_at": now_iso(),
        "candidate_id": candidate.get("id"),
        "plan_version": video.get("plan_version") or 0,
    }
    video["chatgpt_qc"] = result
    if decision == "pass":
        video["status"] = "等待人工审核"
        video["bottleneck"] = None
        video["auto_action"] = "ChatGPT内容质检已通过，只等待老板最终审核"
    else:
        video["status"] = "等待ChatGPT策划"
        video["bottleneck"] = "ChatGPT内容质检要求重做"
        video["auto_action"] = "携带本次质检原因和镜头反馈自动重新策划下一版本"
    _event(data, "chatgpt_content_qc", video_id=video.get("id"), campaign_id=video.get("campaign_id"), detail=result)
    cf._save(data)
    return video


def record_candidate(payload):
    data = cf._load()
    video = cf._by_id(data.get("videos", []), cf._clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    local_path = cf._clean(payload.get("local_path"), "成片路径", 500)
    candidate = {
        "id": cf._id("CUT"), "created_at": now_iso(), "local_path": local_path,
        "exists": Path(local_path).is_file(), "duration_seconds": payload.get("duration_seconds"),
        "quality_notes": cf._clean(payload.get("quality_notes"), "质检说明", 800, False),
        "ai_score": payload.get("ai_score"),
        "technical_qc": payload.get("technical_qc"),
        "source_summary": payload.get("source_summary") or [],
        "enhancements": payload.get("enhancements") if isinstance(payload.get("enhancements"), dict) else {},
    }
    video.setdefault("candidates", []).append(candidate)
    video["technical_qc"] = candidate.get("technical_qc")
    passed = bool(candidate["exists"] and (candidate.get("technical_qc") or {}).get("passed", True))
    if passed:
        video["status"] = "等待ChatGPT质检"
        video["bottleneck"] = "等待ChatGPT执行内容质检"
        video["auto_action"] = "自动把技术质检、素材来源和FINAL.MP4证据回传ChatGPT；通过后再交老板审核"
        video["chatgpt_qc"] = {"status": "pending", "candidate_id": candidate["id"], "requested_at": now_iso()}
    else:
        video["status"] = "异常待处理"
        video["bottleneck"] = "技术质检未通过"
        video["auto_action"] = "本地执行器将按失败策略重新处理"
    _event(data, "final_candidate_created", video_id=video.get("id"), campaign_id=video.get("campaign_id"), detail={
        "candidate_id": candidate["id"], "technical_qc_passed": passed,
    })
    cf._save(data)
    return candidate


def review_video(payload):
    video = _ORIGINAL["review_video"](payload)
    data = cf._load()
    current = cf._by_id(data.get("videos", []), video["id"], "视频任务")
    decision = str((current.get("review") or {}).get("decision") or "")
    if decision == "退回重做":
        current["status"] = "等待ChatGPT策划"
        current["bottleneck"] = "老板已退回当前成片，等待ChatGPT重新策划"
        current["auto_action"] = "自动携带上一版方案、ChatGPT质检和老板意见生成下一版本"
    _event(data, "owner_final_review", video_id=current.get("id"), campaign_id=current.get("campaign_id"), detail=current.get("review") or {})
    cf._save(data)
    return current


def create_publish_plan(payload):
    data = cf._load()
    video = cf._by_id(data.get("videos", []), cf._clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    account = cf._by_id(data.get("accounts", []), cf._clean(payload.get("account_id"), "账号ID", 64), "账号")
    suggested = platform_rules.suggested_publish_fields(video, account.get("platform"))
    values = dict(payload)
    values["title"] = str(payload.get("title") or suggested.get("title") or "").strip()
    values["caption"] = str(payload.get("caption") or suggested.get("caption") or video.get("cta") or "").strip()
    values["scheduled_for"] = str(payload.get("scheduled_for") or suggested.get("scheduled_for") or "").strip()
    rule_check = platform_rules.evaluate(video, account, values["title"], values["caption"])
    if not rule_check["passed"]:
        raise ValueError("发布前硬规则未通过：" + "；".join(rule_check["hard_issues"]))
    plan = _ORIGINAL["create_publish_plan"](values)
    data = cf._load()
    current = cf._by_id(data.get("publication_plans", []), plan["id"], "发布计划")
    current["rule_check"] = rule_check
    current["strategy_source"] = suggested.get("source")
    current["platform_adaptation"] = suggested
    _event(data, "publish_plan_created", video_id=current.get("video_id"), campaign_id=current.get("campaign_id"), detail={
        "plan_id": current.get("id"), "platform": current.get("platform"), "rule_check": rule_check,
    })
    cf._save(data)
    return current


def record_receipt(payload):
    receipt = _ORIGINAL["record_receipt"](payload)
    data = cf._load()
    plan = cf._by_id(data.get("publication_plans", []), receipt.get("plan_id"), "发布计划")
    learning = platform_rules.record_outcome(plan.get("platform"), receipt.get("result"), {
        "plan_id": plan.get("id"), "video_id": plan.get("video_id"), "reason": receipt.get("reason"),
    })
    _event(data, "publication_receipt", video_id=plan.get("video_id"), campaign_id=plan.get("campaign_id"), detail={
        "result": receipt.get("result"), "platform": plan.get("platform"), "url": receipt.get("url"),
    })
    cf._save(data)
    receipt["learning_summary"] = learning
    return receipt


def update_runtime_state(video_id, **kwargs):
    before = cf._load()
    previous = next((x.get("status") for x in before.get("videos", []) if x.get("id") == video_id), None)
    result = _ORIGINAL["update_runtime_state"](video_id, **kwargs)
    if previous != result.get("status"):
        data = cf._load()
        _event(data, "runtime_state_changed", video_id=result.get("id"), campaign_id=result.get("campaign_id"), detail={
            "from": previous, "to": result.get("status"), "bottleneck": result.get("bottleneck"),
            "auto_action": result.get("auto_action"),
        })
        cf._save(data)
    return result


def dashboard():
    value = _ORIGINAL["dashboard"]()
    from promotion import material_library, media_adapters
    data = cf._load()
    value["chatgpt_handoff"] = pending_chatgpt_handoff()
    value["chatgpt_qc_handoff"] = pending_chatgpt_qc_handoff()
    value["platform_rule_center"] = platform_rules.snapshot()
    value["platform_learning"] = platform_rules.learning_summary()
    value["material_library"] = material_library.status()
    value["media_adapters"] = media_adapters.status()
    value["production_events"] = list(reversed(data.get("events", [])[-100:]))
    return value


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL.update({
        "normalize_contract": cf.normalize_contract,
        "add_asset": cf.add_asset,
        "record_candidate": cf.record_candidate,
        "review_video": cf.review_video,
        "create_publish_plan": cf.create_publish_plan,
        "record_receipt": cf.record_receipt,
        "update_runtime_state": cf.update_runtime_state,
        "dashboard": cf.dashboard,
    })
    cf.normalize_contract = _enhanced_normalize_contract
    cf.add_asset = add_asset
    cf.pending_chatgpt_handoff = pending_chatgpt_handoff
    cf.pending_chatgpt_qc_handoff = pending_chatgpt_qc_handoff
    cf.apply_chatgpt_qc = apply_chatgpt_qc
    cf.record_candidate = record_candidate
    cf.review_video = review_video
    cf.create_publish_plan = create_publish_plan
    cf.record_receipt = record_receipt
    cf.update_runtime_state = update_runtime_state
    cf.dashboard = dashboard

    # Patch import-time aliases held by the HTTP server and asset intake module.
    try:
        from backend import server
        server.factory_add_asset = add_asset
        server.factory_record_candidate = record_candidate
        server.factory_review_video = review_video
        server.factory_create_publish_plan = create_publish_plan
        server.factory_record_receipt = record_receipt
        server.content_factory_dashboard = dashboard
    except (ImportError, AttributeError):
        pass
    try:
        from promotion import asset_intake
        asset_intake.add_asset = add_asset
    except (ImportError, AttributeError):
        pass
    _INSTALLED = True


install()
