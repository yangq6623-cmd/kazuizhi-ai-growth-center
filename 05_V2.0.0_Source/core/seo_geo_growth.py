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
        published = sum(1 for asset in assets if str(asset.get("published_at") or "").startswith(date))
        submitted = sum(
            1 for asset in assets
            if any(str(receipt.get("at") or "").startswith(date) for receipt in (asset.get("submission_receipts") or []))
        )
        if row.get("published") != published or row.get("submitted") != submitted:
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
        path = urlsplit(public_url).path.rstrip("/")
        slug = path.rsplit("/", 1)[-1].removesuffix(".html") or asset_id.lower()
        published_at = str(receipt.get("created_at") or verification.get("checked_at") or now_iso())
        keyword = str(opportunity.get("keyword") or slug)
        data["assets"].append({
            "id": asset_id,
            "opportunity_id": opportunity.get("id") or "",
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
            "events": [{
                "at": published_at,
                "stage": "PUBLISHED",
                "payload": {
                    "public_url": public_url,
                    "deploy_receipt": receipt.get("receipt_id") or "",
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
        data["daily_runs"] = _reconciled_daily_runs(data)
        _save(data)
    return {"restored": restored, "count": len(restored)}


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


def _source_tracking_id(asset):
    """Stable public attribution id that contains no customer information."""
    raw = str(asset.get("id") or asset.get("slug") or asset.get("keyword") or "kazuizhi")
    return f"KZSEO-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12].upper()}"


def _render_page(asset, facts, canonical="", related=None):
    brand = facts.get("brand") or "卡嘴子"
    region = asset.get("region") or DEFAULT_REGION
    service = asset.get("service") or "本地服务"
    keyword = asset.get("keyword") or f"{region}{service}"
    title = f"{keyword}｜{brand}本地服务"
    description = f"在{region}需要{service}时，了解问题描述、价格确认、服务流程和售后留痕。{brand}提供真实的本地需求发布与服务连接入口。"
    canonical = str(canonical or "{{CANONICAL}}")
    site_url = str(facts.get("official_site") or DEFAULT_SITE).rstrip("/") + "/"
    source_id = _source_tracking_id(asset)
    mini_program = str(facts.get("mini_program") or "卡嘴子本地服务")
    updated = datetime.now().date().isoformat()
    faq = [
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
             "provider": {"@id": site_url + "#organization"}},
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
    faq_html = "".join(f"<section><h2>{esc(q)}</h2><p>{esc(a)}</p></section>" for q, a in faq)
    related_html = "".join(
        f'<li><a href="{esc(row.get("url"))}">{esc(row.get("label"))}</a></li>'
        for row in list(related or [])[:4] if row.get("url") and row.get("label")
    )
    if not related_html:
        related_html = f'<li><a href="{esc(site_url)}">返回{esc(brand)}官网</a></li>'
    action_url = f"{site_url}?kz_source={source_id}#/repair"
    schema_json = json.dumps(schema, ensure_ascii=False).replace("</", "<\\/")
    body = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow,max-image-preview:large"><meta name="kazuizhi-source-id" content="{esc(source_id)}"><title>{esc(title)}</title><meta name="description" content="{esc(description)}"><link rel="canonical" href="{esc(canonical)}"><meta property="og:type" content="article"><meta property="og:site_name" content="{esc(brand)}本地服务"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(canonical)}"><script type="application/ld+json">{schema_json}</script><style>body{{margin:0;font:16px/1.75 system-ui,-apple-system,"Microsoft YaHei",sans-serif;color:#172033;background:#f5f8fc}}main{{max-width:880px;margin:auto;padding:28px}}article{{background:#fff;border:1px solid #e3e9f2;border-radius:18px;padding:28px;box-shadow:0 10px 30px rgba(33,76,130,.06)}}h1{{font-size:32px;line-height:1.3}}h2{{margin-top:28px;font-size:21px}}a{{color:#175cd3}}.answer{{font-size:18px;background:#eef6ff;border-left:4px solid #2878ff;padding:16px}}.facts{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding:0;list-style:none}}.facts li{{background:#f7f9fc;padding:12px;border-radius:10px}}.cta{{display:inline-block;margin-top:12px;background:#2878ff;color:white;text-decoration:none;padding:11px 18px;border-radius:10px;font-weight:700}}.proof{{color:#52657d;font-size:14px}}@media(max-width:640px){{main{{padding:12px}}article{{padding:20px}}h1{{font-size:27px}}.facts{{grid-template-columns:1fr}}}}</style></head><body><main><article data-kz-source="{esc(source_id)}"><nav aria-label="面包屑"><a href="{esc(site_url)}">{esc(brand)}</a> / {esc(region)} / {esc(service)}</nav><h1>{esc(keyword)}</h1><p>{esc(description)}</p><section><h2>简短答案</h2><p class="answer">在{esc(region)}需要{esc(service)}时，先说明故障或需求、所在区域和期望时间，再通过{esc(brand)}发布需求。维修项目应先检测、再提交明细报价，用户确认后施工，并保留订单和售后记录。</p><a class="cta" href="{esc(action_url)}" rel="nofollow">前往官网提交需求</a><p class="proof">正式下单入口：微信小程序“{esc(mini_program)}”。来源编号：{esc(source_id)}</p></section><section><h2>服务信息</h2><ul class="facts"><li><strong>服务区域</strong><br>{esc(region)}</li><li><strong>服务类别</strong><br>{esc(service)}</li><li><strong>价格原则</strong><br>现场检测后明细报价，用户确认后施工</li></ul></section><section><h2>建议准备的信息</h2><ol><li>所在小区或服务区域，不在公开页面填写门牌等隐私信息。</li><li>故障现象、发生时间、设备型号或需要完成的事项。</li><li>可安全拍摄的现场照片，以及方便沟通和上门的时间。</li></ol></section><section><h2>服务与售后流程</h2><p>提交需求后，由平台核对服务范围并连接合适的本地服务人员。涉及维修时，检测结果、报价、增项和完工确认应通过正式订单留痕；实际响应与到场时间以双方确认为准。</p></section>{faq_html}<section><h2>相关页面</h2><ul>{related_html}</ul></section><footer><p>更新时间：<time datetime="{updated}">{updated}</time> · 内容来源：{esc(brand)}公开服务规则 · 页面编号：{esc(source_id)}</p><p>本页不虚构固定价格、案例、排名、收录或AI推荐；最终服务范围和费用以真实订单确认为准。</p></footer></article></main></body></html>"""
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
            "today_published_verified": len(published_today),
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
