"""R8-13 truthful SEO/GEO growth domain.

This module is intentionally evidence-gated.  A generated page is not treated
as published, a submitted URL is not treated as indexed, and an AI mention is
never inferred from content generation.  External success is recorded only
when the caller supplies observable evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core.storage import data_root, now_iso, read_json, write_json

STORE = "r8_13/seo_geo_growth.json"
SCHEMA = "kz.seo-geo-growth.v1"
DEFAULT_SITE = "https://kazuizhi.com/"
DEFAULT_REGION = "涟水县"

STAGES = [
    "DISCOVERED", "PLANNED", "GENERATED", "QC_PASSED", "PUBLISHED",
    "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED",
]
STAGE_INDEX = {name: index for index, name in enumerate(STAGES)}

DEFAULT_BRAND_FACTS = {
    "brand": "卡嘴子",
    "positioning": "本地生活服务与维修需求连接平台",
    "primary_region": DEFAULT_REGION,
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


def ensure_baseline():
    data = _load()
    existing = {str(x.get("keyword") or "") for x in data["opportunities"] if isinstance(x, dict)}
    added = 0
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
    if not data["geo_questions"]:
        data["geo_questions"] = _default_geo_questions()
        _audit_event(data, "geo_baseline_created", {"questions": len(data["geo_questions"])})
    if added:
        _audit_event(data, "opportunity_baseline_created", {"added": added})
    _save(data)
    return {"added_opportunities": added, "questions": len(data["geo_questions"])}


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
    data = _load()
    ensure_baseline()
    data = _load()
    configured = int(limit or data["config"].get("daily_page_limit") or 6)
    candidates = [x for x in data["opportunities"] if isinstance(x, dict) and not x.get("asset_id")]
    candidates.sort(key=lambda x: (_priority_score(x.get("priority")), x.get("discovered_at") or ""))
    created = []
    for opportunity in candidates[: max(0, configured)]:
        asset_id = _stable_id("SEO", opportunity["region"], opportunity["service"], opportunity["keyword"])
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
    return {"created": created, "count": len(created)}


def _render_page(asset, facts):
    brand = facts.get("brand") or "卡嘴子"
    region = asset.get("region") or DEFAULT_REGION
    service = asset.get("service") or "本地服务"
    keyword = asset.get("keyword") or f"{region}{service}"
    title = f"{keyword}｜{brand}本地服务"
    description = f"了解{region}{service}需求如何发布、如何说明问题以及如何连接本地服务人员。{brand}提供本地需求发布与服务连接入口。"
    faq = [
        (f"{region}{service}需求怎么发布？", f"可先说明所在区域、具体问题、期望服务时间和可联系信息，再通过{brand}的真实服务入口发布需求。"),
        ("如何提高需求匹配效率？", "尽量描述故障现象、位置、是否紧急以及现场限制；涉及价格与到场时间，以实际沟通和用户确认为准。"),
        (f"{brand}会不会保证固定价格？", "不会。现场服务价格与到场安排需要结合真实情况确认，平台页面不应虚构固定报价、案例或服务承诺。"),
    ]
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": brand, "url": "{{CANONICAL}}"},
            {"@type": "Service", "name": service, "areaServed": region, "provider": {"@type": "Organization", "name": brand}},
            {"@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq
            ]},
        ],
    }
    faq_html = "".join(f"<section><h2>{q}</h2><p>{a}</p></section>" for q, a in faq)
    body = f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{title}</title><meta name=\"description\" content=\"{description}\"><link rel=\"canonical\" href=\"{{{{CANONICAL}}}}\"><script type=\"application/ld+json\">{json.dumps(schema, ensure_ascii=False).replace('{{CANONICAL}}','{{{{CANONICAL}}}}')}</script></head><body><main><nav aria-label=\"breadcrumb\"><a href=\"/\">{brand}</a> / {region} / {service}</nav><h1>{keyword}</h1><p>{description}</p><section><h2>简短答案</h2><p>在{region}需要{service}时，可先把问题、区域和期望服务时间说明清楚，再通过{brand}发布本地服务需求并等待真实服务人员响应。</p></section><section><h2>服务信息</h2><ul><li>服务区域：{region}</li><li>服务类别：{service}</li><li>信息原则：不虚构价格、案例、排名或到场承诺</li></ul></section>{faq_html}<p>更新时间：{datetime.now().date().isoformat()}</p></main></body></html>"""
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
        title, description, html = _render_page(asset, facts)
        html = html.replace("{{CANONICAL}}", canonical)
        folder = staging / "seo" / asset["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "index.html"
        path.write_text(html, encoding="utf-8")
        asset.update({
            "stage": "GENERATED",
            "title": title,
            "description": description,
            "canonical": canonical,
            "staging_path": str(path),
            "generated_at": now_iso(),
            "updated_at": now_iso(),
        })
        generated.append(asset["id"])
    _write_staging_infrastructure(data, staging, site)
    if generated:
        _audit_event(data, "staging_pages_generated", {"asset_ids": generated, "truth": "GENERATED 不等于 PUBLISHED"})
    _save(data)
    return {"generated": generated, "count": len(generated), "staging_root": str(staging)}


def _write_staging_infrastructure(data, staging, site):
    robots = "User-agent: *\nAllow: /\nSitemap: " + urljoin(site, "sitemap.xml") + "\n"
    (staging / "robots.txt").write_text(robots, encoding="utf-8")
    urls = [x.get("canonical") for x in data["assets"] if x.get("canonical")]
    sitemap = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    sitemap += "\n".join(f"  <url><loc>{url}</loc></url>" for url in sorted(set(urls)))
    sitemap += "\n</urlset>\n"
    (staging / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    manifest = {
        "generated_at": now_iso(),
        "site": site,
        "urls": urls,
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
    _audit_event(data, "asset_stage_recorded", {"asset_id": asset_id, "from": current, "to": stage})
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
            "public_pages": published,
            "submitted_urls": submitted,
            "crawled_urls": crawled,
            "indexed_urls": indexed,
            "ranked_urls": ranked,
            "conversions": conversions,
        },
        "funnel": {"generated": counts["generated"], "published": published, "submitted": submitted, "crawled": crawled, "indexed": indexed},
        "geo": _geo_summary(data),
        "opportunities": sorted(deepcopy(opportunities), key=lambda x: (_priority_score(x.get("priority")), x.get("keyword") or ""))[:50],
        "assets": sorted(deepcopy(assets), key=lambda x: x.get("updated_at") or "", reverse=True)[:100],
        "technical": technical_snapshot(),
        "daily_runs": deepcopy(data["daily_runs"][:30]),
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
