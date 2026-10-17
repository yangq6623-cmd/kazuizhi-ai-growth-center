"""Bridge the productized content factory into the existing R8 growth-ops ledger.

New content-factory campaigns use the exact same KZ Growth ID in the durable R8
growth-ops state. This avoids the previous split where content pages showed one
Growth ID while consultation/order records used another namespace.

The bridge never invents business outcomes. It only exposes leads and order
attribution already stored by the truthful R8 growth-ops APIs.
"""
from __future__ import annotations

import hashlib

from core.storage import now_iso
from core import r8_growth_ops as growth
from promotion import content_factory as cf


_INSTALLED = False
_ORIGINAL = {}


def _ensure_campaign(campaign):
    campaign_id = str(campaign.get("id") or "").strip()
    if not campaign_id:
        return None
    with growth._LOCK:
        state = growth._state()
        existing = next((x for x in state.get("growth_cases", []) if x.get("growth_id") == campaign_id), None)
        if existing:
            return existing
        signal_id = f"SIG-CF-{campaign_id}"[:80]
        signal = next((x for x in state.get("signals", []) if x.get("signal_id") == signal_id), None)
        if not signal:
            summary = str(campaign.get("title") or "本地真实业务问题").strip()
            evidence = str(campaign.get("evidence") or "").strip()
            signal = {
                "signal_id": signal_id,
                "platform": "other",
                "platform_name": "本地业务输入",
                "source_url": None,
                "source_id": campaign_id,
                "author_public_id": None,
                "published_at": None,
                "detected_at": campaign.get("created_at") or now_iso(),
                "region": campaign.get("region") or "",
                "service_category": campaign.get("service") or "",
                "intent_level": "high",
                "urgency": "normal",
                "sentiment": "neutral",
                "risk_level": "normal",
                "summary": (summary + (f"；依据：{evidence}" if evidence else ""))[:1000],
                "recommended_action": "human",
                "dedupe_key": hashlib.sha256(f"content_factory|{campaign_id}".encode("utf-8")).hexdigest()[:32],
                "matched_account_id": None,
                "route_state": "content_factory",
                "status": "routed",
                "created_at": campaign.get("created_at") or now_iso(),
                "updated_at": now_iso(),
                "source_system": "content_factory",
            }
            state.setdefault("signals", []).append(signal)
        item = {
            "growth_id": campaign_id,
            "signal_id": signal_id,
            "source": {"platform": "other", "url": None, "source_id": campaign_id},
            "region": campaign.get("region") or "",
            "service_category": campaign.get("service") or "",
            "target_user": "本地真实需求用户",
            "hypothesis": (campaign.get("evidence") or f"围绕“{campaign.get('title') or ''}”提供真实帮助，可形成有效咨询机会")[:500],
            "business_goal": "conversion",
            "status": "planning",
            "content_job_id": None,
            "publish_job_id": None,
            "conclusion": None,
            "created_at": campaign.get("created_at") or now_iso(),
            "updated_at": now_iso(),
            "source_system": "content_factory",
        }
        state.setdefault("growth_cases", []).append(item)
        growth._audit(state, "growth_case_linked", campaign_id, "内容工厂增长ID已与R8咨询/归因账本统一")
        growth._save(state)
        return item


def _sync_all_campaigns():
    data = cf._load()
    for campaign in data.get("campaigns", []):
        _ensure_campaign(campaign)


def create_campaign(payload):
    item = _ORIGINAL["create_campaign"](payload)
    _ensure_campaign(item)
    return item


def _growth_snapshot(active_id):
    with growth._LOCK:
        state = growth._state()
        signal_to_growth = {x.get("signal_id"): x.get("growth_id") for x in state.get("growth_cases", [])}
        all_leads = state.get("leads", [])
        leads = []
        for row in reversed(all_leads):
            gid = signal_to_growth.get(row.get("signal_id"))
            if active_id and gid != active_id:
                continue
            leads.append({
                **row,
                "growth_id": gid,
                "summary": row.get("service_category") or "本地服务咨询",
                "service": row.get("service_category"),
                "owner": row.get("account_id") or "未分配",
                "status": row.get("stage") or "new",
                "last_contact_at": row.get("updated_at") or row.get("first_touch_at"),
                "next_action": row.get("next_follow_up_at") or ("等待人工处理" if row.get("stage") == "human_required" else "按线索状态继续跟进"),
            })
        all_lead_growth = {
            row.get("lead_id"): signal_to_growth.get(row.get("signal_id"))
            for row in all_leads
        }
        attribution = []
        for row in reversed(state.get("attribution", [])):
            gid = all_lead_growth.get(row.get("lead_id"))
            if active_id and gid != active_id:
                continue
            attribution.append({**row, "growth_id": gid})
        metrics = [x for x in state.get("metric_snapshots", []) if not active_id or x.get("growth_id") == active_id]
        return {
            "leads": leads[:200],
            "attribution": attribution[:200],
            "metric_snapshots": list(reversed(metrics[-200:])),
            "lead_count": len(leads),
            "order_count": sum(1 for x in attribution if x.get("order_status") != "cancelled"),
            "completed_order_count": sum(1 for x in attribution if x.get("order_status") == "completed"),
            "source": "r8_growth_ops",
        }


def dashboard():
    _sync_all_campaigns()
    value = _ORIGINAL["dashboard"]()
    active_id = value.get("active_campaign_id")
    snapshot = _growth_snapshot(active_id)
    value["leads"] = snapshot["leads"]
    value["attribution"] = snapshot["attribution"]
    value["metric_snapshots"] = snapshot["metric_snapshots"]
    value["conversion_summary"] = {
        "growth_id": active_id,
        "consultations": snapshot["lead_count"] if snapshot["lead_count"] else None,
        "orders": snapshot["order_count"] if snapshot["attribution"] else None,
        "completed_orders": snapshot["completed_order_count"] if snapshot["attribution"] else None,
        "mini_program_requests": None,
        "quotes": None,
        "source": snapshot["source"],
        "truth_note": "只有R8真实线索或已记录订单归因才显示数字；没有来源时保持未接入。",
    }
    return value


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL.update({"create_campaign": cf.create_campaign, "dashboard": cf.dashboard})
    cf.create_campaign = create_campaign
    cf.dashboard = dashboard
    from backend import server
    server.factory_create_campaign = create_campaign
    server.content_factory_dashboard = dashboard
    _INSTALLED = True


install()
