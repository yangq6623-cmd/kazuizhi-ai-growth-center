"""R8-18 cross-module growth evidence ledger.

The ledger deliberately separates local work from external outcomes.  It can
import existing R8-13/R8-16/mission/business records, but never changes an
asset's SEO stage and never treats a local task as a public-platform receipt.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy

from analytics.business_metrics import build_analytics
from core.mission_ledger import snapshot as mission_ledger_snapshot
from core.seo_geo_growth import dashboard as seo_dashboard
from core.storage import now_iso, read_json, write_json
from integrations.business_data import business_source_status
from integrations.search_engine_submitter import status as search_submit_status

STORE = "r8_18/growth_evidence.json"
SCHEMA = "kz.growth-evidence.v1"
MAX_EVENTS = 2000


def _empty():
    return {"schema": SCHEMA, "updated_at": "", "events": [], "imports": {}}


def _load():
    data = read_json(STORE, _empty())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = _empty()
    data.setdefault("events", [])
    data.setdefault("imports", {})
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _event_id(kind, source, reference, observed_at):
    seed = "|".join((str(kind), str(source), str(reference), str(observed_at)))
    return "EVD-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()


def _append(data, *, kind, source, reference, observed_at, payload, external=False):
    event_id = _event_id(kind, source, reference, observed_at)
    if any(row.get("id") == event_id for row in data["events"]):
        return False
    data["events"].insert(0, {
        "id": event_id,
        "kind": kind,
        "source": source,
        "reference": str(reference or ""),
        "observed_at": str(observed_at or now_iso()),
        "external": bool(external),
        "payload": deepcopy(payload) if isinstance(payload, dict) else {"value": payload},
        "recorded_at": now_iso(),
    })
    return True


def _legacy_events():
    """Build import candidates from existing truthful module state."""
    rows = []
    seo = seo_dashboard()
    for asset in seo.get("assets") or []:
        asset_id = asset.get("id")
        for receipt in asset.get("submission_receipts") or []:
            rows.append({"kind": "search_submission_receipt", "source": "r8_16_search_submitter", "reference": f"{asset_id}:{receipt.get('engine')}:{receipt.get('receipt')}", "observed_at": receipt.get("at"), "payload": {"asset_id": asset_id, "engine": receipt.get("engine"), "receipt": receipt.get("receipt"), "public_url": asset.get("public_url")}, "external": True})
        for evidence in asset.get("crawl_evidence") or []:
            rows.append({"kind": "crawl_evidence", "source": "r8_13_seo_geo", "reference": asset_id, "observed_at": evidence.get("at"), "payload": {"asset_id": asset_id, "evidence": evidence.get("evidence"), "public_url": asset.get("public_url")}, "external": True})
        for evidence in asset.get("index_evidence") or []:
            rows.append({"kind": "index_evidence", "source": "r8_13_seo_geo", "reference": asset_id, "observed_at": evidence.get("at"), "payload": {"asset_id": asset_id, "evidence": evidence.get("evidence"), "public_url": asset.get("public_url")}, "external": True})
        for mention in asset.get("geo_mentions") or []:
            rows.append({"kind": "geo_observation", "source": "r8_13_seo_geo", "reference": asset_id, "observed_at": mention.get("at"), "payload": {"asset_id": asset_id, "provider": mention.get("provider"), "type": mention.get("type"), "evidence": mention.get("evidence"), "source_url": mention.get("source_url")}, "external": True})

    search = search_submit_status()
    last_result = search.get("last_result") or {}
    if last_result:
        rows.append({"kind": "search_connector_run", "source": "r8_16_search_submitter", "reference": str(search.get("last_run_at") or "latest"), "observed_at": search.get("last_run_at"), "payload": {"submitted_count": last_result.get("submitted_count", 0), "failed_count": last_result.get("failed_count", 0), "baidu_quota_hold": last_result.get("baidu_quota_hold", False)}, "external": False})

    metrics = build_analytics()
    source = business_source_status(metrics)
    if source.get("status") == "connected":
        rows.append({"kind": "business_snapshot", "source": "verified_business_readonly", "reference": str(source.get("remote_as_of") or "latest"), "observed_at": source.get("remote_as_of"), "payload": {"source": source.get("source"), "data_quality": source.get("data_quality"), "analytics_status": metrics.get("status")}, "external": True})

    ledger = mission_ledger_snapshot()
    for mission in ledger.get("missions") or []:
        receipt = mission.get("latest_platform_receipt") if isinstance(mission, dict) else None
        if not isinstance(receipt, dict):
            continue
        rows.append({"kind": "mission_receipt", "source": "mission_ledger", "reference": receipt.get("receipt_id") or receipt.get("id") or "", "observed_at": receipt.get("at") or receipt.get("created_at"), "payload": receipt, "external": bool(receipt.get("url") and receipt.get("platform_content_id"))})
    return rows


def refresh_legacy_import():
    """Idempotently import evidence already produced by trusted modules."""
    data = _load()
    added = 0
    for row in _legacy_events():
        if _append(data, **row):
            added += 1
    data["imports"]["legacy"] = {"at": now_iso(), "added": added}
    _save(data)
    return {"added": added, "total": len(data["events"]), "truth": "只导入已有可追溯证据；本地任务、草稿和连接配置不会被伪装成外部成果。"}


def status(limit=100):
    data = _load()
    events = list(data.get("events") or [])[:max(1, min(int(limit or 100), 500))]
    summary = {"total": len(data.get("events") or []), "external": 0, "by_kind": {}}
    for row in data.get("events") or []:
        if row.get("external"):
            summary["external"] += 1
        kind = str(row.get("kind") or "unknown")
        summary["by_kind"][kind] = int(summary["by_kind"].get(kind) or 0) + 1
    return {
        "schema": SCHEMA,
        "updated_at": data.get("updated_at") or "",
        "summary": summary,
        "events": events,
        "imports": deepcopy(data.get("imports") or {}),
        "truth": "总账只显示来源、时间与可追溯引用。SUBMITTED、CRAWLED、INDEXED、排名、AI引用和订单归因互不替代。",
    }
