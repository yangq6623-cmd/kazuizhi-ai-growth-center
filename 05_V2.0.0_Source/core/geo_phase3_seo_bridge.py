"""Phase-3 bridge from evidence-derived GEO gaps into targeted SEO assets.

The bridge is additive and idempotent.  It never marks an asset published or
submitted.  It only creates the exact Phase-3 SEO asset, writes its staging
page, and applies deterministic local QC.  Existing real deployment/search
connectors remain solely responsible for PUBLISHED/SUBMITTED truth states.
"""
from __future__ import annotations

from urllib.parse import urljoin

from core import seo_geo_growth
from core.storage import data_root, now_iso


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


def _asset_for_opportunity(data, opportunity):
    asset_id = str(opportunity.get("asset_id") or "")
    if asset_id:
        existing = next((row for row in data.get("assets") or [] if str(row.get("id") or "") == asset_id), None)
        if existing:
            return existing, False
    asset_id = seo_geo_growth._stable_id(
        "SEO", opportunity.get("region"), opportunity.get("service"), opportunity.get("keyword")
    )
    existing = next((row for row in data.get("assets") or [] if str(row.get("id") or "") == asset_id), None)
    if existing:
        opportunity["asset_id"] = asset_id
        opportunity["status"] = existing.get("stage") or "PLANNED"
        return existing, False
    asset = {
        "id": asset_id,
        "opportunity_id": opportunity["id"],
        "region": opportunity.get("region") or seo_geo_growth.DEFAULT_REGION,
        "service": opportunity.get("service") or "综合维修",
        "keyword": opportunity.get("keyword") or "本地服务",
        "intent": opportunity.get("intent") or "GEO缺口修复",
        "priority": opportunity.get("priority") or "S",
        "page_type": seo_geo_growth._page_type_for(opportunity),
        "slug": seo_geo_growth._slug(
            f"{opportunity.get('region','')}-{opportunity.get('service','')}-{opportunity.get('keyword','')}"
        ),
        "stage": "PLANNED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "public_url": "",
        "canonical": "",
        "submission_receipts": [],
        "crawl_evidence": [],
        "index_evidence": [],
        "rankings": [],
        "geo_mentions": [],
        "conversions": [],
        "phase3_source": opportunity.get("phase3_source") or "GEO Phase 3",
        "phase3_source_ref": opportunity.get("phase3_source_ref") or "",
    }
    data.setdefault("assets", []).append(asset)
    opportunity["asset_id"] = asset_id
    opportunity["status"] = "PLANNED"
    return asset, True


def prepare_phase3_assets(plan):
    """Target completed Phase-3 actions before the general daily SEO queue.

    This prevents old/baseline opportunities from consuming the daily limit and
    leaving a completed GEO optimization action stuck at DISCOVERED.  The helper
    deliberately stops at QC_PASSED; real deployment and search submission are
    still performed by the existing verified connectors.
    """
    actions = [
        row for row in (plan or {}).get("actions") or []
        if str(row.get("job_state") or "") == "completed" and row.get("opportunity_id")
    ]
    if not actions:
        return {"targeted": 0, "created": [], "generated": [], "qc_passed": [], "states": []}

    action_by_opportunity = {
        str(row.get("opportunity_id")): row for row in actions if row.get("opportunity_id")
    }
    target_ids = set(action_by_opportunity)
    data = seo_geo_growth._load()
    opportunities = {
        str(row.get("id") or ""): row for row in data.get("opportunities") or [] if isinstance(row, dict)
    }
    created = []
    target_assets = []
    for opportunity_id in target_ids:
        opportunity = opportunities.get(opportunity_id)
        if not opportunity:
            continue
        asset, was_created = _asset_for_opportunity(data, opportunity)
        action = action_by_opportunity.get(opportunity_id) or {}
        action_id = str(action.get("action_id") or "")
        # Persist only public-safe, factual optimization context.  This makes a
        # reused service page a real content revision instead of repeatedly
        # attaching new GEO work to an unchanged historic publication.
        asset["growth_action_id"] = action_id
        asset["growth_question"] = str(action.get("question_text") or "")[:240]
        asset["growth_focus"] = str(action.get("decision") or "")[:240]
        asset["growth_question_id"] = str(action.get("question_id") or "")[:120]
        asset["content_revision_id"] = action_id
        target_assets.append(asset.get("id"))
        if was_created:
            created.append(asset.get("id"))
    if created:
        seo_geo_growth._audit_event(data, "geo_phase3_assets_planned", {"asset_ids": created})
    seo_geo_growth._save(data)

    data = seo_geo_growth._load()
    site = str(data.get("config", {}).get("site_base_url") or seo_geo_growth.DEFAULT_SITE).rstrip("/") + "/"
    staging = data_root() / "r8_13" / "site_staging"
    staging.mkdir(parents=True, exist_ok=True)
    generated = []
    refreshed = []
    target_set = {str(value) for value in target_assets if value}
    for asset in data.get("assets") or []:
        if str(asset.get("id") or "") not in target_set:
            continue
        stage = str(asset.get("stage") or "")
        action_id = str(asset.get("growth_action_id") or "")
        is_external = seo_geo_growth.STAGE_INDEX.get(stage, 0) >= seo_geo_growth.STAGE_INDEX["PUBLISHED"]
        verified_for_action = any(
            isinstance(event, dict)
            and str(event.get("growth_action_id") or event.get("content_revision_id") or "") == action_id
            and bool(event.get("deploy_receipt"))
            and str(event.get("public_url") or "").startswith(("https://", "http://"))
            for event in (asset.get("content_refresh_events") or [])
        )
        already_prepared = bool(
            action_id
            and str(asset.get("prepared_growth_action_id") or "") == action_id
            and (
                asset.get("republish_pending")
                or stage in {"GENERATED", "QC_PASSED"}
                or verified_for_action
            )
        )
        if stage != "PLANNED" and not is_external:
            continue
        if already_prepared:
            continue
        canonical = urljoin(site, f"seo/{asset['slug']}/")
        related = [
            {"label": row.get("keyword") or row.get("service"), "url": urljoin(site, f"seo/{row.get('slug')}/")}
            for row in data.get("assets") or []
            if row.get("id") != asset.get("id") and row.get("slug")
            and (row.get("region") == asset.get("region") or row.get("service") == asset.get("service"))
        ]
        title, description, html = seo_geo_growth._render_page(
            asset,
            data.get("brand_facts") or seo_geo_growth.DEFAULT_BRAND_FACTS,
            canonical=canonical,
            related=related,
        )
        folder = staging / "seo" / asset["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "index.html"
        path.write_text(html, encoding="utf-8")
        rendered_at = now_iso()
        asset.update({
            "title": title,
            "description": description,
            "canonical": canonical,
            "staging_path": str(path),
            # Rebuilding an already-public Asset is a revision, not a new
            # generated Asset.  Preserve its original generation identity so
            # today's SEO counters cannot be inflated by a GEO refresh loop.
            "generated_at": (
                asset.get("generated_at")
                or asset.get("created_at")
                or asset.get("published_at")
                or rendered_at
            ) if is_external else rendered_at,
            "updated_at": rendered_at,
            # The HTML was rendered by the installed template, so the durable
            # verification contract must advance with it.  Keeping the legacy
            # value makes a valid republish fail after public HTTP verification.
            "public_template_version": seo_geo_growth.PUBLIC_TEMPLATE_VERSION,
            "phase3_targeted": True,
            "prepared_growth_action_id": action_id,
        })
        if is_external:
            asset["last_staging_refresh_at"] = rendered_at
            # Preserve durable external truth.  The deployer clears this flag
            # only after a new public HTTP receipt verifies the revision.
            asset["republish_pending"] = True
            asset["republish_requested_at"] = now_iso()
            refreshed.append(asset["id"])
        else:
            asset["stage"] = "GENERATED"
            generated.append(asset["id"])
    seo_geo_growth._write_staging_infrastructure(data, staging, site)
    if generated:
        seo_geo_growth._audit_event(data, "geo_phase3_assets_generated", {"asset_ids": generated, "truth": "GENERATED 不等于 PUBLISHED"})
    if refreshed:
        seo_geo_growth._audit_event(data, "geo_growth_content_revision_prepared", {
            "asset_ids": refreshed,
            "truth": "旧页面外部状态保持不变；新版本必须取得新的真实公网发布回执。",
        })
    seo_geo_growth._save(data)

    qc_passed = []
    snap = seo_geo_growth.dashboard()
    for asset in snap.get("assets") or []:
        if str(asset.get("id") or "") not in target_set or str(asset.get("stage") or "") != "GENERATED":
            continue
        canonical = str(asset.get("canonical") or "")
        staging_path = str(asset.get("staging_path") or "")
        if not asset.get("title") or not asset.get("description") or not canonical.startswith(("http://", "https://")) or not staging_path:
            continue
        seo_geo_growth.record_asset_stage(asset["id"], "QC_PASSED", {
            "local_qc": "GEO Phase 3 targeted deterministic SEO page QC",
            "checked_at": now_iso(),
        })
        qc_passed.append(asset["id"])

    final = seo_geo_growth.dashboard()
    states = [
        {
            "asset_id": row.get("id"),
            "stage": row.get("stage"),
            "public_url": row.get("public_url") or "",
            "republish_pending": bool(row.get("republish_pending")),
            "content_revision_id": row.get("content_revision_id") or "",
            "last_republished_at": row.get("last_republished_at") or "",
        }
        for row in final.get("assets") or [] if str(row.get("id") or "") in target_set
    ]
    return {
        "targeted": len(target_set),
        "created": created,
        "generated": generated,
        "refreshed": refreshed,
        "qc_passed": qc_passed,
        "states": states,
        "truth": "桥接只推进到QC_PASSED；PUBLISHED/SUBMITTED仍必须由真实连接器取得回执。",
    }


seo_geo_growth.upsert_opportunity = upsert_opportunity
seo_geo_growth.prepare_phase3_assets = prepare_phase3_assets
