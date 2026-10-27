"""R8-13 truthful SEO/GEO growth domain.

This module is intentionally evidence-gated.  A generated page is not treated
as published, a submitted URL is not treated as indexed, and an AI mention is
never inferred from content generation.  External success is recorded only
when the caller supplies observable evidence.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit

from core.storage import data_root, now_iso, read_json, write_json
from core import seo_content_quality

STORE = "r8_13/seo_geo_growth.json"
SCHEMA = "kz.seo-geo-growth.v1"
DEFAULT_SITE = "https://kazuizhi.com/"
DEFAULT_REGION = "涟水县"
PUBLIC_TEMPLATE_VERSION = "R8-31-mini-program-primary-v5"


def _template_revision(value):
    """Return the monotonic R8 template revision, or -1 when unknown.

    The public ledger is durable across application upgrades.  A newer
    template marker must therefore never be treated as "legacy" merely
    because an older executable does not recognize the full version string.
    """
    match = re.match(r"^R8-(\d+)(?:-|$)", str(value or "").strip(), flags=re.I)
    return int(match.group(1)) if match else -1

STAGES = [
    "DISCOVERED", "PLANNED", "GENERATED", "QC_PASSED", "PUBLISHED",
    "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED",
]
STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}

DEFAULT_BRAND_FACTS = {
    "brand": "卡嘴子",
    "positioning": "本地生活服务与维修需求连接平台",
    "primary_region": DEFAULT_REGION,
    "mini_program": "卡嘴子本地服务",
    "mini_program_app_id": "wxcc5ca2cefb937dba",
    "mini_program_original_id": "gh_81812d9605fa",
    "mini_program_default_path": "pages/index/index",
    "services": ["水电安装维修", "家电维修", "管道疏通", "安装服务", "个人任务"],
    "truth_rule": "只发布可验证的品牌、区域、服务与业务事实，不伪造案例、价格、排名、收录或AI引用。",
}

DEFAULT_OPPORTUNITIES = [
    ("涟水县", "水电安装维修", "涟水县水电维修", "交易", "S"),
    ("涟水县", "水电安装维修", "涟水水管漏水维修", "紧急交易", "S"),
    ("涟水县", "水电安装维修", "涟水跳闸维修", "交易", "A"),
    ("涟水县", "管道疏通", "涟水管道疏通", "交易", "S"),
    ("涟水县", "家电维修", "涟水家电维修上门", "交易", "A"),
    ("涟水县", "安装服务", "涟水安装师傅", "交易", "A"),
    ("涟水县", "水电安装维修", "水管漏水怎么办", "信息", "A"),
    ("涟水县", "水电安装维修", "家里跳闸怎么办", "信息", "A"),
    ("涟水县", "个人任务", "涟水本地兼职任务", "交易", "B"),
    ("淮安市", "家电维修", "淮安家电维修上门", "交易", "B"),
]


def _empty_state():
    return {
        "schema": SCHEMA,
        "updated_at": now_iso(),
        "config": {
            "site_base_url": DEFAULT_SITE,
            "primary_region": DEFAULT_REGION,
            "daily_page_limit": 6,
            "auto_plan_enabled": True,
            "auto_stage_enabled": True,
            "external_publish_enabled": False,
        },
        "brand_facts": deepcopy(DEFAULT_BRAND_FACTS),
        "opportunities": [],
        "assets": [],
        "technical_runs": [],
        "submission_events": [],
        "geo_questions": [],
        "geo_observations": [],
        "daily_runs": [],
        "audit": [],
    }


def _load():
    data = read_json(STORE, _empty_state())
    if not isinstance(data, dict):
        data = _empty_state()
    data.setdefault("schema", SCHEMA)
    data.setdefault("config", _empty_state()["config"])
    data.setdefault("brand_facts", deepcopy(DEFAULT_BRAND_FACTS))
    if not isinstance(data.get("brand_facts"), dict):
        data["brand_facts"] = deepcopy(DEFAULT_BRAND_FACTS)
    else:
        for key, value in DEFAULT_BRAND_FACTS.items():
            data["brand_facts"].setdefault(key, deepcopy(value))
    for key in ("opportunities", "assets", "technical_runs", "submission_events", "geo_questions", "geo_observations", "daily_runs", "audit"):
        data.setdefault(key, [])
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _stable_id(prefix, *parts):
    raw = "|".join(str(x or "") for x in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def _slug(text):
    ascii_part = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    if ascii_part:
        return ascii_part[:80]
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:16]


def _stage_at_least(asset, stage):
    return STAGE_INDEX.get(str(asset.get("stage") or "DISCOVERED"), 0) >= STAGE_INDEX[stage]


def _priority_score(value):
    return {"S": 0, "A": 1, "B": 2, "C": 3}.get(str(value).upper(), 9)


def _audit_event(data, kind, detail):
    data["audit"].insert(0, {"at": now_iso(), "kind": kind, "detail": detail})
    data["audit"] = data["audit"][:500]


def _daily_generation_breakdown(data, date):
    """Separate first generation from revisions of an existing Asset.

    Before #857, ``refresh_legacy_staging`` overwrote ``generated_at``.  Eight
    existing public Assets refreshed on #856 were consequently shown as eight
    brand-new generations.  The audit ledger still preserves the refresh event,
    so old rows can be classified truthfully without rewriting history.
    """
    date = str(date or "")
    refreshed = set()
    for event in data.get("audit") or []:
        if not isinstance(event, dict) or event.get("kind") != "legacy_public_pages_rebuilt":
            continue
        if not str(event.get("at") or "").startswith(date):
            continue
        detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
        refreshed.update(str(value) for value in (detail.get("asset_ids") or []) if value)
    generated_ids = []
    updated_ids = []
    new_count = 0
    updated_count = 0
    for asset in data.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id") or "")
        updated_today = (
            str(asset.get("last_staging_refresh_at") or "").startswith(date)
            or bool(asset_id and asset_id in refreshed)
        )
        if updated_today:
            updated_count += 1
            if asset_id:
                updated_ids.append(asset_id)
        elif str(asset.get("generated_at") or "").startswith(date):
            # Legacy/import fixtures may not have an Asset ID yet.  They still
            # count as generated rows, while the inspectable ID list omits the
            # missing identifier instead of inventing one.
            new_count += 1
            if asset_id:
                generated_ids.append(asset_id)
    return {
        "new_asset_ids": sorted(set(generated_ids)),
        "updated_asset_ids": sorted(set(updated_ids)),
        "new_count": new_count,
        "updated_count": updated_count,
    }


def _reconciled_daily_runs(data):
    """Derive each day's publish/submit figures from the immutable asset ledger.

    A daily cycle starts before the public deploy and search submit workers run.
    Its original row therefore records zero for those later stages.  The owner
    UI must show the actual receipts, not that stale start-of-cycle snapshot.
    """
    assets = list(data.get("assets") or [])
    rows = []
    for raw in data.get("daily_runs") or []:
        row = deepcopy(raw)
        date = str(row.get("date") or "")
        if not date:
            rows.append(row)
            continue
        planned = sum(1 for asset in assets if str(asset.get("created_at") or "").startswith(date))
        generation = _daily_generation_breakdown(data, date)
        generated = generation["new_count"]
        updated = generation["updated_count"]
        published = sum(1 for asset in assets if str(asset.get("published_at") or "").startswith(date))
        submitted = sum(
            1 for asset in assets
            if any(str(receipt.get("at") or "").startswith(date) for receipt in (asset.get("submission_receipts") or []))
        )
        if (row.get("planned") != planned or row.get("generated") != generated
                or row.get("updated") != updated
                or row.get("published") != published or row.get("submitted") != submitted):
            row["planned"] = planned
            row["generated"] = generated
            row["updated"] = updated
            row["published"] = published
            row["submitted"] = submitted
            row["receipt_reconciled"] = True
        rows.append(row)
    return rows


def reconcile_external_publish_enabled(publish_connector_ready=False):
    """Persist the effective publish state after a verified Remote Agent setup.

    Older installs can have a working R8-17 Remote Agent while retaining the
    legacy R8-13 flag as false.  Once the connector is live and at least one
    real public receipt exists, align the flag without treating configuration
    alone as a publication success.
    """
    data = _load()
    has_verified_publication = any(
        _stage_at_least(asset, "PUBLISHED") and str(asset.get("public_url") or "").startswith(("http://", "https://"))
        for asset in (data.get("assets") or [])
    )
    changed = False
    if bool(publish_connector_ready) and has_verified_publication and not data["config"].get("external_publish_enabled"):
        data["config"]["external_publish_enabled"] = True
        _audit_event(data, "external_publish_state_reconciled", {"source": "verified_remote_or_public_connector"})
        changed = True
    reconciled_runs = _reconciled_daily_runs(data)
    if reconciled_runs != data.get("daily_runs"):
        data["daily_runs"] = reconciled_runs
        changed = True
    if changed:
        _save(data)
    return deepcopy(data["config"])


def rehydrate_verified_publications(receipts):
    """Recover missing local asset rows from immutable verified deploy receipts.

    This migration is intentionally narrow: it restores only the public URL,
    verification result and receipt timestamp that are already independently
    recorded by R8-15/R8-17.  It does not recreate local source files, claim a
    content generation timestamp, or infer any search-engine submission.
    """
    data = _load()
    existing = {str(row.get("id") or "") for row in data["assets"] if isinstance(row, dict)}
    opportunities = {
        str(row.get("id") or "").replace("KW-", "SEO-", 1): row
        for row in data["opportunities"]
        if isinstance(row, dict)
    }
    # A deploy Receipt is durable even when an interrupted/concurrent ledger
    # write loses the richer SEO row. The GEO growth ledger still owns the
    # exact region/service/keyword tuple and the revision that was deployed.
    # Recover only when that tuple hashes back to the same Asset ID.
    growth = read_json("geo_validation/growth_orchestrator.json", {"opportunities": []})
    growth_rows = growth.get("opportunities") if isinstance(growth, dict) else []
    growth_by_asset = {}
    growth_by_revision = {}
    for row in growth_rows or []:
        if not isinstance(row, dict):
            continue
        region = str(row.get("region") or "").strip()
        service = str(row.get("service") or "").strip()
        keyword = str(row.get("keyword") or "").strip()
        asset_id = str(row.get("asset_id") or "").strip()
        if not all((region, service, keyword, asset_id)):
            continue
        if _stable_id("SEO", region, service, keyword) != asset_id:
            continue
        growth_by_asset[asset_id] = row
        revision_id = str(row.get("content_revision_id") or row.get("id") or "").strip()
        if revision_id:
            growth_by_revision[revision_id] = row

    receipt_by_asset = {}
    for receipt in list(receipts or []):
        if not isinstance(receipt, dict):
            continue
        asset_id = str(receipt.get("asset_id") or "").strip()
        if asset_id and bool((receipt.get("verification") or {}).get("ok")):
            receipt_by_asset.setdefault(asset_id, receipt)

    def recovery_source(asset_id, receipt=None):
        receipt = receipt if isinstance(receipt, dict) else {}
        snapshot = receipt.get("asset_snapshot") if isinstance(receipt.get("asset_snapshot"), dict) else {}
        candidates = [
            (snapshot, "verified_deploy_receipt_asset_snapshot"),
            (growth_by_asset.get(asset_id) or {}, "geo_growth_asset_link"),
            (
                growth_by_revision.get(str(
                    receipt.get("content_revision_id") or receipt.get("growth_action_id") or ""
                )) or {},
                "geo_growth_revision_link",
            ),
            (opportunities.get(asset_id) or {}, "seo_opportunity_link"),
        ]
        for source, label in candidates:
            region = str(source.get("region") or "").strip()
            service = str(source.get("service") or "").strip()
            keyword = str(source.get("keyword") or "").strip()
            if not all((region, service, keyword)):
                continue
            if _stable_id("SEO", region, service, keyword) != asset_id:
                continue
            return source, label
        return {}, ""

    repaired = []
    for asset in data["assets"]:
        if not isinstance(asset, dict):
            continue
        asset_id = str(asset.get("id") or "").strip()
        keyword = str(asset.get("keyword") or "").strip()
        machine_keyword = bool(
            not keyword
            or keyword == str(asset.get("slug") or "").strip()
            or re.fullmatch(r"[0-9a-fA-F]{12,64}", keyword)
        )
        if not asset_id or not (
            machine_keyword or not asset.get("region") or not asset.get("service")
        ):
            continue
        source, source_label = recovery_source(asset_id, receipt_by_asset.get(asset_id))
        if not source:
            asset["metadata_recovery_state"] = "waiting_exact_source"
            continue
        asset.update({
            "opportunity_id": str(source.get("seo_opportunity_id") or source.get("id") or asset.get("opportunity_id") or ""),
            "region": str(source.get("region") or ""),
            "service": str(source.get("service") or ""),
            "keyword": str(source.get("keyword") or ""),
            "intent": str(source.get("intent") or asset.get("intent") or "GEO运营优化"),
            "priority": str(source.get("priority") or asset.get("priority") or ""),
            "page_type": _page_type_for(source),
            "metadata_recovery_state": "exact_source_matched",
            "metadata_recovery_source": source_label,
            "metadata_recovered_at": now_iso(),
            # Preserve the public URL and Receipt truth, but require a fresh
            # verified content revision before declaring the repair public.
            "metadata_repair_pending": _stage_at_least(asset, "PUBLISHED"),
        })
        repaired.append(asset_id)
    restored = []
    seen = set()
    for receipt in list(receipts or []):
        if not isinstance(receipt, dict):
            continue
        asset_id = str(receipt.get("asset_id") or "").strip()
        public_url = str(receipt.get("public_url") or "").strip()
        verification = receipt.get("verification") or {}
        if (
            not asset_id or asset_id in existing or asset_id in seen
            or not public_url.startswith("https://") or not bool(verification.get("ok"))
        ):
            continue
        opportunity = opportunities.get(asset_id) or {}
        source, source_label = recovery_source(asset_id, receipt)
        if source:
            opportunity = source
        path = urlsplit(public_url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1].removesuffix(".html") or asset_id.lower()
        published_at = str(receipt.get("created_at") or verification.get("checked_at") or now_iso())
        keyword = str(opportunity.get("keyword") or slug)
        publication_event_id = "PUBLICATION-" + hashlib.sha256(
            str(receipt.get("receipt_id") or "").encode("utf-8")
        ).hexdigest()[:16].upper()
        data["assets"].append({
            "id": asset_id,
            "opportunity_id": opportunity.get("seo_opportunity_id") or opportunity.get("id") or "",
            "region": opportunity.get("region") or "",
            "service": opportunity.get("service") or "",
            "keyword": keyword,
            "intent": opportunity.get("intent") or "",
            "priority": opportunity.get("priority") or "",
            "page_type": _page_type_for(opportunity) if opportunity else "已恢复公开页",
            "slug": slug,
            "stage": "PUBLISHED",
            "created_at": "",
            "updated_at": published_at,
            "published_at": published_at,
            "public_url": public_url,
            "canonical": str(verification.get("canonical") or public_url),
            "staging_path": "",
            "title": keyword,
            "description": "",
            "submission_receipts": [],
            "crawl_evidence": [],
            "index_evidence": [],
            "rankings": [],
            "geo_mentions": [],
            "conversions": [],
            "metadata_recovery_state": "exact_source_matched" if source else "waiting_exact_source",
            "metadata_recovery_source": source_label,
            "metadata_recovered_at": now_iso() if source else "",
            "metadata_repair_pending": bool(source),
            "events": [{
                "at": published_at,
                "stage": "PUBLISHED",
                "payload": {
                    "public_url": public_url,
                    "deploy_receipt": receipt.get("receipt_id") or "",
                    "publication_event_id": publication_event_id,
                    "recovered_from_verified_receipt": True,
                },
            }],
        })
        if opportunity:
            opportunity["asset_id"] = asset_id
            opportunity["status"] = "PUBLISHED"
        existing.add(asset_id)
        seen.add(asset_id)
        restored.append(asset_id)
    if restored:
        _audit_event(data, "verified_publication_ledger_rehydrated", {"asset_ids": restored})
    if repaired:
        _audit_event(data, "verified_asset_metadata_recovered", {
            "asset_ids": repaired,
            "truth": "仅恢复通过Asset ID指纹校验的GEO/SEO元数据；原URL、状态和Receipt不变。",
        })
    if restored or repaired:
        data["daily_runs"] = _reconciled_daily_runs(data)
        _save(data)
    return {
        "restored": restored,
        "count": len(restored),
        "metadata_repaired": repaired,
        "metadata_repaired_count": len(repaired),
    }


def ensure_baseline():
    data = _load()
    existing = {str(x.get("keyword") or "") for x in data["opportunities"] if isinstance(x, dict)}
    added = 0
    changed = False
    for region, service, keyword, intent, priority in DEFAULT_OPPORTUNITIES:
        if keyword in existing:
            continue
        data["opportunities"].append({
            "id": _stable_id("KW", region, service, keyword),
            "region": region,
            "service": service,
            "keyword": keyword,
            "intent": intent,
            "priority": priority,
            "status": "DISCOVERED",
            "source": "R8-13 baseline / 本地业务事实",
            "discovered_at": now_iso(),
            "asset_id": "",
        })
        added += 1
        changed = True
    if not data["geo_questions"]:
        data["geo_questions"] = _default_geo_questions()
        _audit_event(data, "geo_baseline_created", {"questions": len(data["geo_questions"])})
        changed = True
    if added:
        _audit_event(data, "opportunity_baseline_created", {"added": added})
    # Dashboard polling calls ensure_baseline. Once the baseline exists it must
    # remain read-only; otherwise every 30-second refresh competes with workers
    # for the same Windows JSON file.
    if changed:
        _save(data)
    return {"added_opportunities": added, "questions": len(data["geo_questions"]), "changed": changed}


def _default_geo_questions():
    services = ["水电维修", "水管漏水维修", "管道疏通", "家电维修", "安装服务"]
    templates = [
        "{region}哪里可以找{service}师傅？",
        "{region}{service}怎么找比较方便？",
        "{region}有本地{service}平台吗？",
        "{region}{service}需求怎么发布？",
        "在{region}找{service}需要注意什么？",
        "卡嘴子能不能发布{service}需求？",
        "卡嘴子在{region}提供哪些本地服务？",
        "{region}{service}可以在线找师傅吗？",
        "{region}{service}如何比较报价？",
        "{region}本地维修平台怎么选？",
    ]
    rows = []
    for service in services:
        for template in templates:
            question = template.format(region=DEFAULT_REGION, service=service)
            rows.append({
                "id": _stable_id("GEOQ", question),
                "question": question,
                "region": DEFAULT_REGION,
                "service": service,
                "status": "UNTESTED",
            })
    return rows[:50]


def _page_type_for(opportunity):
    intent = str(opportunity.get("intent") or "")
    keyword = str(opportunity.get("keyword") or "")
    if "怎么办" in keyword or intent == "信息":
        return "FAQ页"
    if opportunity.get("region") and opportunity.get("service"):
        return "地区×服务页"
    return "服务页"


def plan_today(limit=None):
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        data = _load()
        ensure_baseline()
        data = _load()
        configured = int(limit or data["config"].get("daily_page_limit") or 6)
        candidates = [x for x in data["opportunities"] if isinstance(x, dict) and not x.get("asset_id")]
        discovery = {"created": False, "reason": "existing_unbound_opportunity"}
        if not candidates:
            discovery = discover_verified_incremental_opportunity()
            data = _load()
            candidates = [x for x in data["opportunities"] if isinstance(x, dict) and not x.get("asset_id")]
        candidates.sort(key=lambda x: (_priority_score(x.get("priority")), x.get("discovered_at") or ""))
        created = []
        for opportunity in candidates[: max(0, configured)]:
            asset_id = _stable_id("SEO", opportunity["region"], opportunity["service"], opportunity["keyword"])
            verified_scope = verified_incremental_publication_scope({}, opportunity)
            asset = {
                "id": asset_id,
                "opportunity_id": opportunity["id"],
                "region": opportunity["region"],
                "service": opportunity["service"],
                "keyword": opportunity["keyword"],
                "intent": opportunity["intent"],
                "priority": opportunity["priority"],
                "page_type": _page_type_for(opportunity),
                "slug": _slug(f"{opportunity['region']}-{opportunity['service']}-{opportunity['keyword']}"),
                "stage": "PLANNED",
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "opportunity_source": str(opportunity.get("source") or ""),
                "publish_approved": verified_scope,
                "publish_approval_source": (
                    "autonomous_verified_service_intent_pool" if verified_scope else ""
                ),
                "public_url": "",
                "canonical": "",
                "submission_receipts": [],
                "crawl_evidence": [],
                "index_evidence": [],
                "rankings": [],
                "geo_mentions": [],
                "conversions": [],
            }
            data["assets"].append(asset)
            opportunity["asset_id"] = asset_id
            opportunity["status"] = "PLANNED"
            created.append(asset_id)
        if created:
            _audit_event(data, "daily_assets_planned", {"asset_ids": created})
        _save(data)
        return {"created": created, "count": len(created), "discovery": discovery}



_OWNER_SEO_ALTERNATES = (
    ("涟水县空调不制冷上门维修", "家电维修"),
    ("涟水县洗衣机不排水上门维修", "家电维修"),
    ("涟水县热水器不加热上门维修", "家电维修"),
    ("涟水县厨房下水管堵塞疏通", "管道疏通"),
    ("涟水县家里跳闸上门检修", "水电安装维修"),
)

# Small, owner-safe discovery pool used only after every persisted Opportunity
# already has an Asset. These are concrete high-intent variants inside the
# verified Lianshui service catalogue; they are not demand-volume estimates.
VERIFIED_INCREMENTAL_OPPORTUNITIES = _OWNER_SEO_ALTERNATES


def verified_incremental_publication_scope(asset, opportunity=None):
    """Recognize only the bounded autonomous SEO pool introduced in #859."""
    asset = asset if isinstance(asset, dict) else {}
    opportunity = opportunity if isinstance(opportunity, dict) else {}
    source = str(
        asset.get("opportunity_source")
        or asset.get("publish_approval_source")
        or opportunity.get("source")
        or ""
    ).strip()
    if source != "autonomous_verified_service_intent_pool":
        return False
    region = str(asset.get("region") or opportunity.get("region") or "").strip()
    service = str(asset.get("service") or opportunity.get("service") or "").strip()
    keyword = str(asset.get("keyword") or opportunity.get("keyword") or "").strip()
    return bool(
        region == DEFAULT_REGION
        and (keyword, service) in VERIFIED_INCREMENTAL_OPPORTUNITIES
    )


def _owner_seo_service(keyword):
    keyword = str(keyword or "")
    if any(x in keyword for x in ("空调", "洗衣机", "冰箱", "热水器", "家电")):
        return "家电维修"
    if any(x in keyword for x in ("下水", "疏通", "马桶", "堵塞")):
        return "管道疏通"
    if any(x in keyword for x in ("跳闸", "水电", "漏水", "插座")):
        return "水电安装维修"
    if any(x in keyword for x in ("安装", "灯具", "家具")):
        return "安装服务"
    return ""


def _normalized_keyword(value):
    return re.sub(r"\s+", "", str(value or "")).strip().lower()


def _keyword_intent_covered(candidate, existing):
    """Conservatively collapse obvious same-appliance/same-fault variants."""
    target = _normalized_keyword(candidate)
    if target in existing:
        return True
    fault_groups = (
        ("空调", "不制冷"),
        ("洗衣机", "不排水"),
        ("热水器", "不加热"),
        ("厨房", "下水", "堵"),
        ("家里", "跳闸"),
    )
    for tokens in fault_groups:
        if all(token in target for token in tokens):
            return any(all(token in item for token in tokens) for item in existing)
    return False


def discover_verified_incremental_opportunity(date=None):
    """Persist at most one new, de-duplicated Opportunity per natural day.

    ``plan_today`` historically stopped forever once all baseline rows were
    bound to Assets. This bounded discovery step restores a real next input
    without inventing demand volume or removing daily/idempotency limits. It
    never creates, publishes or submits an Asset itself.
    """
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        data = _load()
        date = str(date or datetime.now().astimezone().date().isoformat())
        if any(
            isinstance(event, dict)
            and event.get("kind") == "verified_incremental_opportunity_discovered"
            and str(event.get("at") or "").startswith(date)
            for event in data.get("audit") or []
        ):
            return {"created": False, "reason": "daily_incremental_discovery_already_recorded"}
        if any(isinstance(row, dict) and not row.get("asset_id") for row in data.get("opportunities") or []):
            return {"created": False, "reason": "existing_unbound_opportunity"}

        brand_services = set((data.get("brand_facts") or {}).get("services") or [])
        existing = {
            _normalized_keyword(item.get("keyword"))
            for collection in ("assets", "opportunities")
            for item in data.get(collection, []) if isinstance(item, dict) and item.get("keyword")
        }
        selected = next((
            (keyword, service)
            for keyword, service in VERIFIED_INCREMENTAL_OPPORTUNITIES
            if service in brand_services and not _keyword_intent_covered(keyword, existing)
        ), None)
        if not selected:
            return {"created": False, "reason": "verified_incremental_pool_exhausted"}

        keyword, service = selected
        opportunity_id = _stable_id("KW", DEFAULT_REGION, service, keyword)
        opportunity = {
            "id": opportunity_id,
            "region": DEFAULT_REGION,
            "service": service,
            "keyword": keyword,
            "intent": "交易",
            "priority": "S",
            "status": "DISCOVERED",
            "source": "autonomous_verified_service_intent_pool",
            "discovered_at": now_iso(),
            "asset_id": "",
        }
        data["opportunities"].append(opportunity)
        _audit_event(data, "verified_incremental_opportunity_discovered", {
            "opportunity_id": opportunity_id,
            "keyword": keyword,
            "service": service,
            "date": date,
            "truth": "服务范围内去重机会；尚未生成、QC、发布或提交。",
        })
        _save(data)
        return {
            "created": True,
            "reason": "verified_incremental_opportunity_created",
            "opportunity_id": opportunity_id,
            "keyword": keyword,
            "service": service,
        }



def select_owner_seo_incremental_keyword(keyword):
    """Select an uncovered owner keyword before creating the matching draft.

    Exact and common same-fault paraphrases share one search intent. This
    routine is read-only; a later asset write rechecks the ledger.
    """
    keyword = str(keyword or "").strip()
    service = _owner_seo_service(keyword)
    data = _load()
    brand_services = (data.get("brand_facts") or {}).get("services", [])
    if not keyword or len(keyword) > 100 or service not in brand_services:
        return {"keyword": keyword, "service": service, "reason": "service_not_in_verified_brand_scope"}
    existing = [
        _normalized_keyword(item.get("keyword"))
        for collection in ("assets", "opportunities")
        for item in data.get(collection, []) if isinstance(item, dict)
    ]
    def covered(candidate):
        return _keyword_intent_covered(candidate, existing)
    choices = [(keyword, service)] + [row for row in _OWNER_SEO_ALTERNATES if row[0] != keyword]
    for candidate, candidate_service in choices:
        if candidate_service in brand_services and not covered(candidate):
            return {"keyword": candidate, "service": candidate_service, "reason": "selected"}
    return {"keyword": keyword, "service": service, "reason": "all_candidate_keywords_already_covered"}



def plan_owner_seo_incremental_asset(*, command_id, mission_id, keyword, draft_id, publish_requested=False):
    """Create at most one new eligible SEO asset per owner Command.

    This only records a PLANNED asset. Existing autonomous staging, QC,
    scope-controlled public deployment and verified search submission remain
    the sole route to external results. Never count a planned item as public.
    """
    command_id = str(command_id or "").strip()
    mission_id = str(mission_id or "").strip()
    keyword = str(keyword or "").strip()
    draft_id = str(draft_id or "").strip()
    if not all((command_id, mission_id, keyword, draft_id)) or len(keyword) > 100:
        raise ValueError("老板 SEO 增量任务缺少有效来源、目标关键词或草稿ID")
    data = _load()
    # A restart or a retired R7 job must not create a second content asset
    # for the same Command, even if its original keyword has changed.
    for asset in data.get("assets", []):
        if isinstance(asset, dict) and asset.get("owner_command_id") == command_id:
            return {"created": False, "asset_id": asset["id"], "keyword": asset["keyword"], "reason": "existing_owner_asset"}

    region = DEFAULT_REGION
    service = _owner_seo_service(keyword)
    if not service or service not in (data.get("brand_facts") or {}).get("services", []):
        return {"created": False, "asset_id": "", "keyword": keyword, "reason": "service_not_in_verified_brand_scope"}
    selection = select_owner_seo_incremental_keyword(keyword)
    if selection["reason"] != "selected":
        return {"created": False, "asset_id": "", "keyword": keyword, "reason": selection["reason"]}
    target_keyword, service = selection["keyword"], selection["service"]
    # A draft and the planned asset must be about the same selected intent.
    if target_keyword != keyword:
        return {"created": False, "asset_id": "", "keyword": target_keyword,
                "reason": "selected_keyword_mismatch_with_draft"}
    opportunity_id = _stable_id("KW", region, service, target_keyword)
    asset_id = _stable_id("SEO", region, service, target_keyword)
    if any(str(item.get("id")) == asset_id for item in data.get("assets", [])):
        return {"created": False, "asset_id": "", "keyword": target_keyword, "reason": "asset_id_already_exists"}
    opportunity = {
        "id": opportunity_id,
        "region": region, "service": service, "keyword": target_keyword,
        "intent": "交易", "priority": "S", "status": "PLANNED",
        "source": "owner_authorized_r7_seo_incremental", "owner_command_id": command_id,
        "mission_id": mission_id, "discovered_at": now_iso(), "asset_id": asset_id,
    }
    asset = {
        "id": asset_id, "opportunity_id": opportunity_id,
        "region": region, "service": service, "keyword": target_keyword,
        "intent": "交易", "priority": "S", "page_type": "地区×服务页",
        "slug": _slug(f"{region}-{service}-{target_keyword}"),
        "stage": "PLANNED", "created_at": now_iso(), "updated_at": now_iso(),
        "owner_command_id": command_id, "mission_id": mission_id,
        "owner_draft_id": draft_id, "owner_requested_keyword": keyword,
        # Only explicit owner's request to publish a page in an existing,
        # verified service scope can unlock the existing deployment gate.
        "publish_approved": bool(publish_requested),
        "publish_approval_source": ("owner_command_known_brand_scope" if publish_requested else ""),
        "public_url": "", "canonical": "", "submission_receipts": [],
        "crawl_evidence": [], "index_evidence": [], "rankings": [],
        "geo_mentions": [], "conversions": [],
    }
    data["opportunities"].append(opportunity)
    data["assets"].append(asset)
    _audit_event(data, "owner_seo_incremental_asset_planned", {
        "asset_id": asset_id, "opportunity_id": opportunity_id,
        "command_id": command_id, "mission_id": mission_id, "draft_id": draft_id,
        "keyword": target_keyword, "publish_approved": bool(publish_requested),
        "truth": "PLANNED 不等于 GENERATED、QC、PUBLISHED 或 SUBMITTED",
    })
    _save(data)
    return {"created": True, "asset_id": asset_id, "keyword": target_keyword,
            "opportunity_id": opportunity_id, "stage": "PLANNED", "publish_approved": bool(publish_requested)}



def _source_tracking_id(asset):
    """Stable public attribution id that contains no customer information."""
    raw = str(asset.get("id") or asset.get("slug") or asset.get("keyword") or "kazuizhi")
    return f"KZSEO-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def source_tracking_id(asset):
    """Public, deterministic source id used by attribution reconciliation."""
    return _source_tracking_id(asset if isinstance(asset, dict) else {})


def _human_keyword(asset):
    """Keep machine slugs and recovered receipt ids out of public headings."""
    region = str(asset.get("region") or DEFAULT_REGION).strip()
    service = str(asset.get("service") or "本地服务").strip()
    keyword = str(asset.get("keyword") or "").strip()
    slug = str(asset.get("slug") or "").strip()
    machine_value = bool(
        not keyword
        or keyword == slug
        or re.fullmatch(r"[0-9a-fA-F]{12,64}", keyword)
        or re.fullmatch(r"(?:SEO|KW)-[A-Z0-9-]{8,}", keyword)
    )
    return f"{region}{service}需求发布与办理指南" if machine_value else keyword


def _service_guidance(service):
    text = str(service or "")
    if "水电" in text or "漏水" in text:
        return {
            "fit": "适合水管漏水、跳闸、开关插座、灯具与室内水电安装维修等需要本地人员上门处理的需求。",
            "first": "漏水先关闭对应阀门，电路异常先远离带电区域；存在人身风险时先联系物业、供电或应急部门。",
        }
    if "家电" in text:
        return {
            "fit": "适合需要本地师傅检测空调、洗衣机、热水器等家电故障，或比较上门检测与维修方案的需求。",
            "first": "仍在保修期的家电应先联系品牌官方售后；涉及燃气或明显焦糊味时停止使用并保持通风。",
        }
    if "疏通" in text:
        return {
            "fit": "适合厨房、卫生间、地漏及室内排水不畅等需要现场判断和疏通的需求。",
            "first": "先停止继续排水并说明堵塞位置、返水情况和是否使用过疏通剂，避免不同化学剂混用。",
        }
    if "安装" in text:
        return {
            "fit": "适合灯具、卫浴、家具及其他需要本地人员上门安装、拆装或调试的需求。",
            "first": "提前准备品牌型号、尺寸、安装位置和现场照片，并确认是否涉及打孔、拆旧、搬运或高空作业。",
        }
    if "个人任务" in text:
        return {
            "fit": "适合时间、地点、工作内容和验收标准明确的邻里互助或本地小任务。",
            "first": "不要在公开描述中填写身份证、门牌、银行卡等敏感信息；费用、时间与责任应在正式沟通中确认。",
        }
    return {
        "fit": "适合需要在本地区域发布明确需求、连接合适服务人员并保留沟通与订单记录的场景。",
        "first": "先写清区域、问题、期望时间和验收要求；紧急公共设施或人身安全问题应优先联系对应管理或应急部门。",
    }


def _public_hero_image(asset, site_url):
    """Return a same-site professional image URL; never treat the QR as hero."""
    raw = str((asset or {}).get("hero_image_url") or "").strip()
    if not raw:
        return ""
    resolved = urljoin(site_url, raw)
    parts = urlsplit(resolved)
    site_parts = urlsplit(site_url)
    path = parts.path.lower()
    if parts.scheme.lower() != "https" or parts.netloc.lower() != site_parts.netloc.lower():
        return ""
    if not re.search(r"\.(?:jpe?g|png|webp)$", path):
        return ""
    if "kazuizhi-mini-program-code" in path:
        return ""
    return resolved


def _render_page(asset, facts, canonical="", related=None):
    brand = facts.get("brand") or "卡嘴子"
    region = asset.get("region") or DEFAULT_REGION
    service = asset.get("service") or "本地服务"
    keyword = _human_keyword(asset)
    title = f"{keyword}｜{brand}本地服务"
    description = f"{brand}是面向{region}的本地需求发布与服务连接平台。关于“{keyword}”，本页说明{service}的适用场景、准备事项、费用确认和正式入口。"
    page_copy = seo_content_quality.page_copy(service, keyword, region, brand)
    canonical = str(canonical or "{{CANONICAL}}")
    site_url = str(facts.get("official_site") or DEFAULT_SITE).rstrip("/") + "/"
    source_id = _source_tracking_id(asset)
    mini_program = str(facts.get("mini_program") or "卡嘴子本地服务")
    asset_id = str(asset.get("id") or "").strip()
    action_url = urljoin(
        site_url,
        "open/?kz_source=%s&asset_id=%s"
        % (quote(source_id, safe=""), quote(asset_id, safe="")),
    )
    repair_url = f"{site_url}?kz_source={quote(source_id, safe='')}#/repair"
    mini_code_url = urljoin(site_url, "seo/assets/kazuizhi-mini-program-code.jpg")
    hero_image_url = _public_hero_image(asset, site_url)
    growth_question = str(asset.get("growth_question") or "").strip()[:240]
    growth_focus = str(asset.get("growth_focus") or "").strip()[:240]
    updated = datetime.now().date().isoformat()
    faq = [
        (page_copy["faq_question"], page_copy["faq_answer"]),
        (f"{region}{service}需求怎么发布？", f"可先说明所在区域、具体问题、期望服务时间和可联系信息，再通过{brand}的真实服务入口发布需求。"),
        ("如何提高需求匹配效率？", "尽量描述故障现象、位置、是否紧急以及现场限制；涉及价格与到场时间，以实际沟通和用户确认为准。"),
        (f"{brand}会不会保证固定价格？", "不会。现场服务价格与到场安排需要结合真实情况确认，平台页面不应虚构固定报价、案例或服务承诺。"),
    ]
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": site_url + "#organization", "name": brand, "url": site_url},
            {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical, "name": title,
             "description": description, "dateModified": updated, "inLanguage": "zh-CN"},
            {"@type": "Service", "@id": canonical + "#service", "url": canonical, "name": service,
             "areaServed": {"@type": "AdministrativeArea", "name": region},
             "provider": {"@id": site_url + "#organization"},
             "potentialAction": {"@type": "UseAction", "target": action_url}},
            {"@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": brand, "item": site_url},
                {"@type": "ListItem", "position": 2, "name": region, "item": canonical},
                {"@type": "ListItem", "position": 3, "name": keyword, "item": canonical},
            ]},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq
            ]},
        ],
    }
    esc = lambda value: html.escape(str(value or ""), quote=True)
    hero_meta = f'<meta property="og:image" content="{esc(hero_image_url)}">' if hero_image_url else ""
    hero_html = (
        f'<figure class="service-hero" data-kz-role="professional-hero">'
        f'<img src="{esc(hero_image_url)}" alt="{esc(keyword)}服务场景" '
        f'loading="eager" data-kz-role="professional-hero-image">'
        f'<figcaption>{esc(region)}{esc(service)}专业服务场景图</figcaption></figure>'
        if hero_image_url else ""
    )
    if hero_image_url:
        schema["@graph"][1]["primaryImageOfPage"] = {
            "@type": "ImageObject", "url": hero_image_url,
        }
    faq_html = "".join(f"<section><h2>{esc(q)}</h2><p>{esc(a)}</p></section>" for q, a in faq)
    revision_html = ""
    if growth_question or growth_focus:
        question_html = f"<p><strong>用户常问：</strong>{esc(growth_question)}</p>" if growth_question else ""
        focus_html = f"<p><strong>本次补充：</strong>{esc(growth_focus)}</p>" if growth_focus else ""
        revision_html = (
            '<section data-kz-role="growth-revision"><h2>本轮内容补充</h2>'
            f"{question_html}{focus_html}"
            '<p>以上内容用于帮助用户更准确地了解适用场景和正式需求入口；实际服务仍以真实开放范围、沟通、报价和订单记录为准。</p></section>'
        )
    related_html = "".join(
        f'<li><a href="{esc(row.get("url"))}">{esc(row.get("label"))}</a></li>'
        for row in list(related or [])[:4] if row.get("url") and row.get("label")
    )
    if not related_html:
        related_html = f'<li><a href="{esc(site_url)}">返回{esc(brand)}官网</a></li>'
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow,max-image-preview:large"><meta name="kazuizhi-source-id" content="{esc(source_id)}"><meta name="kazuizhi-template-version" content="{PUBLIC_TEMPLATE_VERSION}"><title>{esc(title)}</title><meta name="description" content="{esc(description)}"><link rel="canonical" href="{esc(canonical)}"><meta property="og:type" content="article"><meta property="og:site_name" content="{esc(brand)}本地服务"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}"><script type="application/ld+json">{schema_json}</script><style>body{{margin:0;font:16px/1.75 system-ui,-apple-system,"Microsoft YaHei",sans-serif;color:#172033;background:#f5f8fc}}main{{max-width:880px;margin:auto;padding:28px}}article{{background:#fff;border:1px solid #e3e9f2;border-radius:18px;padding:28px;box-shadow:0 10px 30px rgba(33,76,130,.06)}}h1{{font-size:32px;line-height:1.3}}h2{{margin-top:28px;font-size:21px}}a{{color:#175cd3}}.answer{{font-size:18px;background:#eef6ff;border-left:4px solid #2878ff;padding:16px}}.fit{{background:#f7f9fc;border:1px solid #e3e9f2;border-radius:12px;padding:14px 16px}}.facts{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:0;list-style:none}}.facts li{{background:#f7f9fc;padding:12px;border-radius:10px}}.cta{{display:inline-block;margin-top:12px;background:#2878ff;color:white;text-decoration:none;padding:11px 18px;border-radius:10px;font-weight:700}}.secondary{{display:inline-block;margin:12px 0 0 12px}}.entry{{display:grid;grid-template-columns:1fr 190px;gap:18px;align-items:center;background:#f5f8ff;border:1px solid #dbe7ff;border-radius:16px;padding:18px;margin-top:18px}}.entry img{{width:180px;height:180px;object-fit:contain;background:#fff;border-radius:12px}}.proof{{color:#52657d;font-size:14px}}@media(max-width:640px){{main{{padding:12px}}article{{padding:20px}}h1{{font-size:27px}}.facts{{grid-template-columns:1fr}}.entry{{grid-template-columns:1fr;text-align:center}}.entry img{{margin:auto}}.secondary{{display:block;margin-left:0}}}}</style></head><body><main><article data-kz-source="{esc(source_id)}"><nav aria-label="面包屑"><a href="{esc(site_url)}">{esc(brand)}</a> / {esc(region)} / {esc(service)}</nav><h1>{esc(keyword)}</h1><p>{esc(description)}</p><section><h2>直接答案</h2><p class="answer">{esc(page_copy["answer"])}</p><a class="cta" href="{esc(action_url)}" data-kz-entry="mini-program">打开卡嘴子小程序</a><a class="secondary" href="{esc(repair_url)}" data-kz-entry="online-repair">{esc(page_copy["action"])}</a><p class="proof">来源编号：{esc(source_id)}</p><div class="entry" data-kz-role="hero"><div><h2>进入微信小程序</h2><p>用微信扫描右侧小程序码，或在微信中搜索“{esc(mini_program)}”。小程序码属于卡嘴子正式品牌素材。</p><p><strong>电脑端：</strong>微信扫码进入；<strong>手机端：</strong>点击上方按钮进入打开页，或保存图片后用微信识别。</p></div><img src="{esc(mini_code_url)}" alt="{esc(mini_program)}微信小程序码" width="180" height="180" loading="lazy" data-kz-role="mini-program-code"></div></section>{revision_html}<section><h2>适合什么情况</h2><p class="fit">{esc(page_copy['fit'])}</p><h2>处理前先做什么</h2><p class="fit">{esc(page_copy['first'])}</p></section><section><h2>服务信息</h2><ul class="facts"><li><strong>服务区域</strong><br>{esc(region)}</li><li><strong>服务类别</strong><br>{esc(service)}</li><li><strong>价格原则</strong><br>{esc(page_copy["price"])}</li></ul></section><section><h2>建议准备的信息</h2><ol><li>所在小区或服务区域，不在公开页面填写门牌等隐私信息。</li><li>{esc(page_copy["prepare"])}</li><li>可安全拍摄的现场照片，以及方便沟通和上门的时间。</li></ol></section><section><h2>服务与售后流程</h2><p>{esc(page_copy["process"])}</p></section>{faq_html}<section><h2>相关页面</h2><ul>{related_html}</ul></section><footer><p>更新时间：<time datetime="{updated}">{updated}</time> · 内容来源：{esc(brand)}公开服务规则 · 页面编号：{esc(source_id)}</p><p>本页不虚构固定价格、案例、排名、收录或AI推荐；最终服务范围和费用以真实订单确认为准。</p></footer></article></main></body></html>"""
    body = body.replace('data-kz-role="hero"', 'data-kz-role="mini-program-entry"', 1)
    if hero_image_url:
        body = body.replace(
            f'<meta property="og:url" content="{esc(canonical)}">',
            f'<meta property="og:url" content="{esc(canonical)}">{hero_meta}',
            1,
        )
        body = body.replace(
            "a{color:#175cd3}",
            "a{color:#175cd3}.service-hero{margin:20px 0}.service-hero img{display:block;width:100%;height:auto;max-height:480px;object-fit:cover;border-radius:14px}.service-hero figcaption{color:#52657d;font-size:14px;margin-top:8px}",
            1,
        )
        body = body.replace(
            f'<p>{esc(description)}</p><section><h2>直接答案</h2>',
            f'<p>{esc(description)}</p>{hero_html}<section><h2>直接答案</h2>',
            1,
        )
    return title, description, body


def generate_staging(limit=6):
    data = _load()
    facts = data.get("brand_facts") or DEFAULT_BRAND_FACTS
    site = str(data["config"].get("site_base_url") or DEFAULT_SITE).rstrip("/") + "/"
    staging = data_root() / "r8_13" / "site_staging"
    staging.mkdir(parents=True, exist_ok=True)
    generated = []
    for asset in data["assets"]:
        if len(generated) >= int(limit):
            break
        if str(asset.get("stage")) != "PLANNED":
            continue
        canonical = urljoin(site, f"seo/{asset['slug']}/")
        related = [
            {"label": row.get("keyword") or row.get("service"), "url": urljoin(site, f"seo/{row.get('slug')}/")}
            for row in data["assets"]
            if row.get("id") != asset.get("id") and row.get("slug")
            and (row.get("region") == asset.get("region") or row.get("service") == asset.get("service"))
        ]
        title, description, html = _render_page(asset, facts, canonical=canonical, related=related)
        folder = staging / "seo" / asset["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "index.html"
        path.write_text(html, encoding="utf-8")
        generated_at = now_iso()
        asset.update({
            "stage": "GENERATED",
            "title": title,
            "description": description,
            "canonical": canonical,
            "staging_path": str(path),
            "generated_at": generated_at,
            "updated_at": generated_at,
            "content_revision_id": _stable_id(
                "SEO-REV", asset.get("id"), PUBLIC_TEMPLATE_VERSION, generated_at,
            ),
            "public_template_version": PUBLIC_TEMPLATE_VERSION,
            "content_quality_revision": seo_content_quality.CONTENT_QUALITY_REVISION,
        })
        generated.append(asset["id"])
    _write_staging_infrastructure(data, staging, site)
    if generated:
        _audit_event(data, "staging_pages_generated", {"asset_ids": generated, "truth": "GENERATED 不等于 PUBLISHED"})
    _save(data)
    return {"generated": generated, "count": len(generated), "staging_root": str(staging)}


def refresh_legacy_staging(limit=10):
    """Rebuild old public assets without falsifying a backwards stage move.

    A page that was already submitted remains SUBMITTED while its HTML is
    refreshed.  ``republish_pending`` is an independent content-revision flag;
    the public deployer clears it only after the new page passes live HTTP,
    canonical, schema, source-tracking and body-length verification.
    """
    data = _load()
    facts = data.get("brand_facts") or DEFAULT_BRAND_FACTS
    site = str(data["config"].get("site_base_url") or DEFAULT_SITE).rstrip("/") + "/"
    staging = data_root() / "r8_13" / "site_staging"
    staging.mkdir(parents=True, exist_ok=True)
    refreshed = []
    for asset in data["assets"]:
        if len(refreshed) >= max(1, min(int(limit or 10), 20)):
            break
        if not asset.get("slug") or not _stage_at_least(asset, "GENERATED"):
            continue
        current_template = str(asset.get("public_template_version") or "")
        targeted_quality_refresh = (
            str(asset.get("slug") or "") in seo_content_quality.TARGETED_QUALITY_REFRESH_SLUGS
            and asset.get("content_quality_revision") != seo_content_quality.CONTENT_QUALITY_REVISION
        )
        targeted_metadata_repair = bool(
            asset.get("metadata_repair_pending")
            and not asset.get("metadata_repair_staged_at")
            and asset.get("metadata_recovery_state") == "exact_source_matched"
        )
        if current_template == PUBLIC_TEMPLATE_VERSION and not targeted_quality_refresh and not targeted_metadata_repair:
            continue
        # Downgrade protection: a stale executable must not rebuild a page
        # whose durable ledger already records a newer R8 template revision.
        if _template_revision(current_template) > _template_revision(PUBLIC_TEMPLATE_VERSION):
            _audit_event(data, "legacy_refresh_downgrade_blocked", {
                "asset_id": asset.get("id"),
                "installed_template": PUBLIC_TEMPLATE_VERSION,
                "ledger_template": current_template,
            })
            continue
        canonical = str(asset.get("canonical") or urljoin(site, f"seo/{asset['slug']}/"))
        related = [
            {"label": row.get("keyword") or row.get("service"), "url": urljoin(site, f"seo/{row.get('slug')}/")}
            for row in data["assets"]
            if row.get("id") != asset.get("id") and row.get("slug")
            and (row.get("region") == asset.get("region") or row.get("service") == asset.get("service"))
        ]
        title, description, page = _render_page(asset, facts, canonical=canonical, related=related)
        folder = staging / "seo" / str(asset["slug"])
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "index.html"
        path.write_text(page, encoding="utf-8")
        refresh_at = now_iso()
        revision_id = _stable_id(
            "SEO-REV", asset.get("id"), PUBLIC_TEMPLATE_VERSION,
            seo_content_quality.CONTENT_QUALITY_REVISION,
        )
        asset.update({
            "title": title,
            "description": description,
            "canonical": canonical,
            "staging_path": str(path),
            # Preserve the first generation timestamp.  A template rebuild is
            # a content revision of the same Asset/canonical URL, not a new
            # Asset and not a fresh-generation event.
            "generated_at": asset.get("generated_at") or asset.get("created_at") or refresh_at,
            "last_staging_refresh_at": refresh_at,
            "updated_at": refresh_at,
            "content_revision_id": revision_id,
            "public_template_version": PUBLIC_TEMPLATE_VERSION,
            "content_quality_revision": seo_content_quality.CONTENT_QUALITY_REVISION,
            "republish_pending": _stage_at_least(asset, "PUBLISHED"),
        })
        if targeted_metadata_repair:
            asset["content_revision_id"] = _stable_id(
                "SEO-META", asset.get("id"), asset.get("region"),
                asset.get("service"), asset.get("keyword"),
            )
            asset["metadata_repair_staged_at"] = refresh_at
        if targeted_quality_refresh:
            quality_revision_id = "QUALITY-" + hashlib.sha256(
                (str(asset.get("id") or "") + "|" + seo_content_quality.CONTENT_QUALITY_REVISION).encode("utf-8")
            ).hexdigest()[:16].upper()
            # Keep the established #841 Receipt/deployer contract: targeted
            # quality repairs use the QUALITY id as the externally visible
            # content revision.  The dedicated field is additive for #857.
            asset["content_revision_id"] = quality_revision_id
            asset["quality_revision_id"] = quality_revision_id
        if asset.get("stage") in {"GENERATED", "QC_PASSED"}:
            asset["stage"] = "GENERATED"
        refreshed.append(str(asset.get("id") or ""))
    _write_staging_infrastructure(data, staging, site)
    if refreshed:
        _audit_event(data, "legacy_public_pages_rebuilt", {
            "asset_ids": refreshed,
            "template_version": PUBLIC_TEMPLATE_VERSION,
            "truth": "已重建本地页面；原外部状态不回退，公网复核通过前不宣称新版本已发布。",
        })
    _save(data)
    return {"refreshed": refreshed, "count": len(refreshed), "template_version": PUBLIC_TEMPLATE_VERSION}


def reconcile_verified_revision(asset_id, receipt):
    """Clear a stale republish flag using an already verified exact receipt.

    This is local reconciliation only.  It never creates a Publication Event,
    never appends a content-refresh event and never performs an external write.
    """
    receipt = dict(receipt or {})
    if not bool((receipt.get("verification") or {}).get("ok")):
        raise ValueError("仅允许使用已通过公网验证的部署回执对账")
    data = _load()
    asset = next((row for row in data["assets"] if str(row.get("id")) == str(asset_id)), None)
    if not asset:
        raise ValueError("SEO/GEO 资产不存在")
    if not _stage_at_least(asset, "PUBLISHED"):
        raise ValueError("未发布资产不能使用历史回执跳过部署")
    revision = str(asset.get("content_revision_id") or "").strip()
    if not revision or str(receipt.get("content_revision_id") or "").strip() != revision:
        raise ValueError("部署回执与当前内容 Revision 不匹配")
    action = str(asset.get("growth_action_id") or "").strip()
    receipt_action = str(receipt.get("growth_action_id") or "").strip()
    if action and receipt_action != action:
        raise ValueError("部署回执与当前 Growth Action 不匹配")
    public_url = str(receipt.get("public_url") or "").strip()
    parts = urlsplit(public_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("部署回执缺少有效公网 URL")
    existing_url = str(asset.get("public_url") or "").strip()
    if existing_url and existing_url.rstrip("/") != public_url.rstrip("/"):
        raise ValueError("部署回执公网 URL 与资产不匹配")
    at = now_iso()
    asset["republish_pending"] = False
    asset["last_reconciled_deploy_receipt"] = str(receipt.get("receipt_id") or "")
    asset["last_reconciled_at"] = at
    asset["updated_at"] = at
    _audit_event(data, "asset_revision_deploy_reconciled", {
        "asset_id": asset_id,
        "growth_action_id": action,
        "content_revision_id": revision,
        "deploy_receipt": asset["last_reconciled_deploy_receipt"],
        "external_request_created": False,
    })
    _save(data)
    return deepcopy(asset)


def reconcile_unchanged_live_content(asset_id, *, content_fingerprint, public_url):
    """Clear a republish request when staged and deployed semantic content match.

    This never creates a Publication Event or external Receipt, so the original
    effective publication time and 24h/72h/7d retest basis remain unchanged.
    """
    fingerprint = str(content_fingerprint or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise ValueError("内容指纹无效")
    public_url = str(public_url or "").strip()
    parts = urlsplit(public_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("缺少有效公网 URL")
    data = _load()
    asset = next((row for row in data["assets"] if str(row.get("id")) == str(asset_id)), None)
    if not asset:
        raise ValueError("SEO/GEO 资产不存在")
    if not _stage_at_least(asset, "PUBLISHED"):
        raise ValueError("未发布资产不能执行相同内容对账")
    existing_url = str(asset.get("public_url") or "").strip()
    if existing_url and existing_url.rstrip("/") != public_url.rstrip("/"):
        raise ValueError("公网 URL 与资产不匹配")
    at = now_iso()
    asset["republish_pending"] = False
    asset["last_semantic_content_fingerprint"] = fingerprint
    asset["last_semantic_reconciled_revision"] = str(asset.get("content_revision_id") or "")
    asset["last_semantic_reconciled_at"] = at
    asset["updated_at"] = at
    _audit_event(data, "asset_unchanged_live_content_reconciled", {
        "asset_id": asset_id,
        "content_revision_id": asset.get("content_revision_id") or "",
        "content_fingerprint": fingerprint,
        "external_request_created": False,
        "publication_event_created": False,
        "retest_basis_changed": False,
    })
    _save(data)
    return deepcopy(asset)


def record_asset_republished(asset_id, payload=None):
    payload = dict(payload or {})
    public_url = str(payload.get("public_url") or "").strip()
    parts = urlsplit(public_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("重新发布必须提供真实可验证的公网URL")
    data = _load()
    asset = next((row for row in data["assets"] if str(row.get("id")) == str(asset_id)), None)
    if not asset:
        raise ValueError("SEO/GEO 资产不存在")
    if not _stage_at_least(asset, "PUBLISHED"):
        raise ValueError("尚未正式发布的资产不能登记重新发布")
    event = {"at": now_iso(), "template_version": PUBLIC_TEMPLATE_VERSION, **deepcopy(payload)}
    event.setdefault("publication_event_id", "PUBLICATION-" + hashlib.sha256(
        "|".join((
            str(asset_id or ""), str(event.get("content_revision_id") or ""),
            str(event.get("deploy_receipt") or ""), str(event.get("at") or ""),
        )).encode("utf-8")
    ).hexdigest()[:16].upper())
    asset.setdefault("content_refresh_events", []).append(event)
    asset["content_refresh_events"] = asset["content_refresh_events"][-20:]
    asset["public_url"] = public_url
    asset["republish_pending"] = False
    asset["public_template_version"] = PUBLIC_TEMPLATE_VERSION
    asset["last_republished_at"] = event["at"]
    asset["updated_at"] = event["at"]
    if asset.get("metadata_repair_pending"):
        asset["metadata_repair_pending"] = False
        asset["metadata_repair_completed_at"] = event["at"]
    _audit_event(data, "asset_content_republished", {
        "asset_id": asset_id,
        "stage_preserved": asset.get("stage"),
        "template_version": PUBLIC_TEMPLATE_VERSION,
    })
    _save(data)
    return deepcopy(asset)


def _write_staging_infrastructure(data, staging, site):
    robots = "User-agent: *\nAllow: /\nSitemap: " + urljoin(site, "sitemap.xml") + "\n"
    (staging / "robots.txt").write_text(robots, encoding="utf-8")
    rows = [x for x in data["assets"] if x.get("canonical")]
    sitemap = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    sitemap += "\n".join(
        f"  <url><loc>{html.escape(str(row.get('canonical')), quote=True)}</loc><lastmod>{str(row.get('updated_at') or now_iso())[:10]}</lastmod></url>"
        for row in sorted(rows, key=lambda item: str(item.get("canonical")))
    )
    sitemap += "\n</urlset>\n"
    (staging / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    manifest = {
        "generated_at": now_iso(),
        "site": site,
        "urls": [x.get("canonical") for x in rows],
        "truth": "这是待部署站点包；只有真实公网URL可访问后才可标记 PUBLISHED。",
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def configure(payload):
    data = _load()
    config = data["config"]
    if "site_base_url" in payload:
        site = str(payload.get("site_base_url") or "").strip()
        parts = urlsplit(site)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("site_base_url 必须是有效 http/https 地址")
        config["site_base_url"] = site.rstrip("/") + "/"
    for key in ("primary_region",):
        if key in payload:
            config[key] = str(payload.get(key) or "").strip()
    if "daily_page_limit" in payload:
        config["daily_page_limit"] = max(1, min(20, int(payload.get("daily_page_limit") or 6)))
    for key in ("auto_plan_enabled", "auto_stage_enabled", "external_publish_enabled"):
        if key in payload:
            config[key] = bool(payload.get(key))
    _audit_event(data, "seo_geo_config_updated", {"keys": sorted(k for k in payload if k in config)})
    _save(data)
    return deepcopy(config)


def _require_evidence(stage, payload):
    if stage == "PUBLISHED":
        url = str(payload.get("public_url") or "").strip()
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("PUBLISHED 必须提供真实可验证的公网URL")
    elif stage == "SUBMITTED":
        if not payload.get("engine") or not payload.get("receipt"):
            raise ValueError("SUBMITTED 必须提供搜索引擎与真实提交回执")
    elif stage == "CRAWLED":
        if not payload.get("crawl_evidence"):
            raise ValueError("CRAWLED 必须提供实际抓取证据")
    elif stage == "INDEXED":
        if not payload.get("index_evidence"):
            raise ValueError("INDEXED 必须提供实际收录证据")
    elif stage == "RANKED":
        rank = int(payload.get("rank") or 0)
        if rank <= 0:
            raise ValueError("RANKED 必须提供真实排名")
    elif stage in {"MENTIONED", "CITED"}:
        if not payload.get("provider") or not payload.get("question") or not payload.get("evidence"):
            raise ValueError(f"{stage} 必须提供平台、问题和真实观察证据")
    elif stage == "CONVERTED":
        if not (payload.get("lead_id") or payload.get("order_id")):
            raise ValueError("CONVERTED 必须关联真实咨询或订单")


def record_asset_stage(asset_id, stage, payload=None):
    payload = payload or {}
    stage = str(stage or "").upper().strip()
    if stage not in STAGE_INDEX:
        raise ValueError("未知 SEO/GEO 状态")
    data = _load()
    asset = next((x for x in data["assets"] if str(x.get("id")) == str(asset_id)), None)
    if not asset:
        raise ValueError("SEO/GEO 资产不存在")
    current = str(asset.get("stage") or "DISCOVERED")
    if STAGE_INDEX[stage] < STAGE_INDEX.get(current, 0):
        raise ValueError("不允许无审计地回退真实外部状态")
    _require_evidence(stage, payload)
    event = {"at": now_iso(), "stage": stage, "payload": deepcopy(payload)}
    asset.setdefault("events", []).append(event)
    asset["stage"] = stage
    asset["updated_at"] = now_iso()
    if stage == "QC_PASSED":
        asset["qc_passed_at"] = now_iso()
        asset["qc_status"] = "passed"
        asset["qc_reasons"] = []
        asset["qc_last_checked_at"] = asset["qc_passed_at"]
    if stage == "PUBLISHED":
        asset["public_url"] = str(payload["public_url"]).strip()
        asset["published_at"] = now_iso()
    if stage == "SUBMITTED":
        receipt = {"at": now_iso(), "engine": payload["engine"], "receipt": payload["receipt"]}
        asset.setdefault("submission_receipts", []).append(receipt)
        data["submission_events"].insert(0, {"asset_id": asset_id, **receipt})
    if stage == "CRAWLED":
        asset.setdefault("crawl_evidence", []).append({"at": now_iso(), "evidence": payload["crawl_evidence"]})
    if stage == "INDEXED":
        asset.setdefault("index_evidence", []).append({"at": now_iso(), "evidence": payload["index_evidence"]})
    if stage == "RANKED":
        asset.setdefault("rankings", []).append({"at": now_iso(), "engine": payload.get("engine"), "rank": int(payload["rank"]), "keyword": payload.get("keyword") or asset.get("keyword")})
    if stage in {"MENTIONED", "CITED"}:
        asset.setdefault("geo_mentions", []).append({"at": now_iso(), "type": stage, "provider": payload["provider"], "question": payload["question"], "evidence": payload["evidence"], "source_url": payload.get("source_url") or ""})
    if stage == "CONVERTED":
        asset.setdefault("conversions", []).append({"at": now_iso(), "lead_id": payload.get("lead_id"), "order_id": payload.get("order_id")})
    # Keep the current-day operational log aligned with real publication and
    # submission receipts as they arrive, rather than leaving it at the values
    # captured before the external workers ran.
    data["daily_runs"] = _reconciled_daily_runs(data)
    _audit_event(data, "asset_stage_recorded", {"asset_id": asset_id, "from": current, "to": stage})
    _save(data)
    return deepcopy(asset)


def record_asset_qc_failure(asset_id, reasons):
    """Persist a truthful QC wait reason without advancing or deleting Asset."""
    data = _load()
    asset = next((x for x in data["assets"] if str(x.get("id")) == str(asset_id)), None)
    if not asset:
        raise ValueError("SEO/GEO 资产不存在")
    clean = [str(reason or "").strip()[:300] for reason in (reasons or []) if str(reason or "").strip()]
    asset["qc_status"] = "failed"
    asset["qc_reasons"] = clean[:20]
    asset["qc_last_checked_at"] = now_iso()
    asset["qc_attempts"] = int(asset.get("qc_attempts") or 0) + 1
    # Stage intentionally stays GENERATED. A failure is not approval and must
    # not remove the original staged file or historical events.
    _audit_event(data, "asset_qc_failed", {"asset_id": asset_id, "reasons": clean[:20]})
    _save(data)
    return deepcopy(asset)


def record_geo_observation(payload):
    data = _load()
    question_id = str(payload.get("question_id") or "").strip()
    question = next((x for x in data["geo_questions"] if x.get("id") == question_id), None)
    if not question:
        raise ValueError("GEO问题不存在")
    provider = str(payload.get("provider") or "").strip()
    if not provider:
        raise ValueError("provider 不能为空")
    observation = {
        "id": _stable_id("GEOOBS", question_id, provider, now_iso()),
        "observed_at": now_iso(),
        "question_id": question_id,
        "question": question["question"],
        "provider": provider,
        "mentioned": bool(payload.get("mentioned")),
        "cited": bool(payload.get("cited")),
        "recommended": bool(payload.get("recommended")),
        "source_url": str(payload.get("source_url") or "").strip(),
        "evidence": str(payload.get("evidence") or "").strip(),
    }
    if (observation["mentioned"] or observation["cited"] or observation["recommended"]) and not observation["evidence"]:
        raise ValueError("正向 GEO 结果必须有真实观察证据")
    data["geo_observations"].insert(0, observation)
    data["geo_observations"] = data["geo_observations"][:1000]
    question["status"] = "TESTED"
    question["last_tested_at"] = observation["observed_at"]
    _save(data)
    return observation


def connector_status():
    return {
        "baidu": {"label": "百度搜索资源平台", "configured": bool(os.environ.get("KZ_BAIDU_SITE_TOKEN")), "mode": "站点验证/URL提交", "secret_exposed": False},
        "bing": {"label": "Bing Webmaster / IndexNow", "configured": bool(os.environ.get("KZ_INDEXNOW_KEY")), "mode": "IndexNow", "secret_exposed": False},
        "google": {"label": "Google Search Console", "configured": bool(os.environ.get("KZ_GSC_SITE_VERIFIED")), "mode": "站点验证/Sitemap", "secret_exposed": False},
    }


def technical_snapshot():
    data = _load()
    latest = data["technical_runs"][0] if data["technical_runs"] else None
    staging = data_root() / "r8_13" / "site_staging"
    return {
        "latest": latest,
        "staging": {
            "robots_generated": (staging / "robots.txt").is_file(),
            "sitemap_generated": (staging / "sitemap.xml").is_file(),
            "manifest_generated": (staging / "manifest.json").is_file(),
        },
        "connectors": connector_status(),
        "truth": "本地生成的 robots/sitemap/schema 不等于公网已部署；公网抓取、收录和排名必须另有证据。",
    }


def record_technical_run(result):
    data = _load()
    row = {"at": now_iso(), **deepcopy(result)}
    data["technical_runs"].insert(0, row)
    data["technical_runs"] = data["technical_runs"][:100]
    _save(data)
    return row


def _geo_summary(data):
    observations = data["geo_observations"]
    tested_ids = {x.get("question_id") for x in observations}
    latest_by_pair = {}
    for row in observations:
        key = (row.get("question_id"), row.get("provider"))
        if key not in latest_by_pair:
            latest_by_pair[key] = row
    latest = list(latest_by_pair.values())
    mentioned = sum(1 for x in latest if x.get("mentioned"))
    cited = sum(1 for x in latest if x.get("cited"))
    recommended = sum(1 for x in latest if x.get("recommended"))
    denominator = len(latest)
    return {
        "questions": len(data["geo_questions"]),
        "tested_questions": len(tested_ids),
        "observations": denominator,
        "mentioned": mentioned,
        "cited": cited,
        "recommended": recommended,
        "mention_rate": round(mentioned * 100 / denominator, 1) if denominator else 0,
        "citation_rate": round(cited * 100 / denominator, 1) if denominator else 0,
    }


def dashboard():
    ensure_baseline()
    data = _load()
    assets = data["assets"]
    counts = {stage.lower(): sum(1 for x in assets if _stage_at_least(x, stage)) for stage in STAGES}
    opportunities = data["opportunities"]
    today = datetime.now().astimezone().date().isoformat()
    discovered_today = sum(1 for x in opportunities if str(x.get("discovered_at") or "").startswith(today))
    planned_today = sum(1 for x in assets if str(x.get("created_at") or "").startswith(today))
    published_today = [
        x for x in assets if str(x.get("published_at") or "").startswith(today)
        and _stage_at_least(x, "PUBLISHED")
        and str(x.get("public_url") or "").startswith(("https://", "http://"))
    ]
    submitted_today = [
        x for x in assets if any(
            str(receipt.get("at") or "").startswith(today)
            for receipt in (x.get("submission_receipts") or []) if isinstance(receipt, dict)
        )
    ]
    generation_today = _daily_generation_breakdown(data, today)
    published = counts["published"]
    submitted = counts["submitted"]
    crawled = counts["crawled"]
    indexed = counts["indexed"]
    ranked = counts["ranked"]
    conversions = sum(len(x.get("conversions") or []) for x in assets)
    return {
        "schema": SCHEMA,
        "config": deepcopy(data["config"]),
        "brand_facts": deepcopy(data["brand_facts"]),
        "summary": {
            "today_opportunities": discovered_today,
            "keyword_total": len(opportunities),
            "today_planned": planned_today,
            "today_generated_new": generation_today["new_count"],
            "today_assets_updated": generation_today["updated_count"],
            "today_published_verified": len(published_today),
            "today_published_scope": "seo_asset_first_publication",
            "today_submitted_receipted": len(submitted_today),
            "public_pages": published,
            "submitted_urls": submitted,
            "crawled_urls": crawled,
            "indexed_urls": indexed,
            "ranked_urls": ranked,
            "conversions": conversions,
        },
        "today_publication_receipts": [
            {"asset_id": x.get("id"), "public_url": x.get("public_url"), "published_at": x.get("published_at")}
            for x in sorted(published_today, key=lambda a: a.get("published_at") or "", reverse=True)[:20]
        ],
        "funnel": {"generated": counts["generated"], "published": published, "submitted": submitted, "crawled": crawled, "indexed": indexed},
        "geo": _geo_summary(data),
        "opportunities": sorted(deepcopy(opportunities), key=lambda x: (_priority_score(x.get("priority")), x.get("keyword") or ""))[:50],
        "assets": sorted(deepcopy(assets), key=lambda x: x.get("updated_at") or "", reverse=True)[:100],
        "technical": technical_snapshot(),
        "daily_runs": _reconciled_daily_runs(data)[:30],
        "truth_rule": "GENERATED ≠ PUBLISHED ≠ SUBMITTED ≠ CRAWLED ≠ INDEXED ≠ RANKED；AI提及/引用与咨询订单同样必须有真实证据。",
    }


def run_daily_cycle(force=False):
    ensure_baseline()
    data = _load()
    today = datetime.now().astimezone().date().isoformat()
    existing = next((x for x in data["daily_runs"] if x.get("date") == today), None)
    if existing and not force:
        return {"skipped": True, "reason": "today_already_started", "run": existing}
    planned = plan_today() if data["config"].get("auto_plan_enabled", True) else {"created": [], "count": 0}
    generated = generate_staging(limit=data["config"].get("daily_page_limit", 6)) if data["config"].get("auto_stage_enabled", True) else {"generated": [], "count": 0}
    data = _load()
    row = {
        "date": today,
        "started_at": now_iso(),
        "planned": planned.get("count", 0),
        "generated": generated.get("count", 0),
        "published": 0,
        "submitted": 0,
        "note": "已启动本地SEO/GEO日循环；公网发布、站长提交、抓取、收录与AI可见性仍按真实回执推进。",
    }
    data["daily_runs"] = [x for x in data["daily_runs"] if x.get("date") != today]
    data["daily_runs"].insert(0, row)
    _audit_event(data, "daily_cycle_started", row)
    _save(data)
    return {"skipped": False, "run": row, "planned": planned, "generated": generated}
