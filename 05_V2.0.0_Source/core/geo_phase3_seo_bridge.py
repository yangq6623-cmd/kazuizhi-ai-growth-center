"""Small Phase-3 bridge that adds evidence-derived opportunities to R8-13 SEO.

It patches one additive helper onto seo_geo_growth without changing the older
R8-13 public API. Existing opportunities/assets are never deleted or rewritten.
"""
from __future__ import annotations

from core import seo_geo_growth
from core.storage import now_iso


def upsert_opportunity(payload):
    data = seo_geo_growth._load()
    region = str((payload or {}).get("region") or seo_geo_growth.DEFAULT_REGION).strip()[:40]
    service = str((payload or {}).get("service") or "综合维修").strip()[:60]
    keyword = str((payload or {}).get("keyword") or f"{region}{service}").strip()[:120]
    intent = str((payload or {}).get("intent") or "GEO缺口修复").strip()[:80]
    priority = str((payload or {}).get("priority") or "S").upper()
    if priority not in {"S", "A", "B", "C"}:
        priority = "S"
    source = str((payload or {}).get("source") or "GEO Phase 3").strip()[:160]
    source_ref = str((payload or {}).get("source_ref") or "").strip()[:160]
    if not keyword:
        raise ValueError("phase3_geo_keyword_required")

    for item in data.get("opportunities") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("region") or "") == region and str(item.get("service") or "") == service and str(item.get("keyword") or "") == keyword:
            item["priority"] = priority
            item["phase3_source"] = source
            item["phase3_source_ref"] = source_ref
            item["updated_at"] = now_iso()
            seo_geo_growth._audit_event(data, "geo_phase3_opportunity_reused", {"opportunity_id": item.get("id"), "source_ref": source_ref})
            seo_geo_growth._save(data)
            return item

    item = {
        "id": seo_geo_growth._stable_id("KW", region, service, keyword),
        "region": region,
        "service": service,
        "keyword": keyword,
        "intent": intent,
        "priority": priority,
        "status": "DISCOVERED",
        "source": source,
        "phase3_source": source,
        "phase3_source_ref": source_ref,
        "discovered_at": now_iso(),
        "updated_at": now_iso(),
        "asset_id": "",
    }
    data.setdefault("opportunities", []).append(item)
    seo_geo_growth._audit_event(data, "geo_phase3_opportunity_added", {"opportunity_id": item["id"], "source_ref": source_ref})
    seo_geo_growth._save(data)
    return item


seo_geo_growth.upsert_opportunity = upsert_opportunity
