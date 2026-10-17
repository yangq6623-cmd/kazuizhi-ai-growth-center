"""Truthful local SEO/GEO audit and reusable answer-pack generation."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core.storage import data_root, now_iso, read_json, write_json
from promotion import content_factory


STORE = "r8/search_growth.json"
DEFAULT_SITE = "https://kazuizhi.com/"

# Dedicated to SEO public-site auditing; does not change GEO browser workers.
_AUDIT_LOCK = threading.Lock()
_AUDIT_IN_FLIGHT = False


def _hours_since(value: str) -> float | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds() / 3600)
    except (TypeError, ValueError, OverflowError):
        return None



def _load():
    data = read_json(STORE, {"audits": [], "packs": []})
    if not isinstance(data, dict):
        data = {"audits": [], "packs": []}
    data.setdefault("audits", [])
    data.setdefault("packs", [])
    return data


def status():
    data = _load()
    latest = data["audits"][0] if data["audits"] else None
    age = _hours_since(latest.get("audited_at")) if isinstance(latest, dict) else None
    return {
        "status": "available", "site": DEFAULT_SITE,
        "latest_audit": latest,
        "latest_audit_age_hours": round(age, 2) if age is not None else None,
        "latest_audit_stale": age is None or age >= 24,
        "automatic_audit": {
            "state": data.get("automatic_audit_state") or "not_started",
            "last_attempt_at": data.get("automatic_audit_last_attempt_at") or "",
            "last_completed_at": data.get("automatic_audit_last_completed_at") or "",
            "last_error": data.get("automatic_audit_last_error") or "",
        },
        "packs": data["packs"][:30],
        "truth_rule": "收录、排名和AI引用只记录实际观察结果；生成内容包不等于已经部署或收录。",
    }


def schedule_automatic_audit(min_hours=24, retry_hours=3):
    """Schedule one bounded SEO-only public audit without blocking the five-minute loop.

    Failed network reads remain visible as errors, never as a healthy site.
    A crashing desktop may retry after the bounded attempt delay.
    """
    global _AUDIT_IN_FLIGHT
    with _AUDIT_LOCK:
        data = _load()
        latest = data["audits"][0] if data["audits"] else None
        age = _hours_since(latest.get("audited_at")) if isinstance(latest, dict) else None
        failed = data.get("automatic_audit_state") in {"degraded", "failed"}
        if _AUDIT_IN_FLIGHT:
            return {"scheduled": False, "reason": "audit_in_progress"}
        if age is not None and age < min_hours and not failed:
            return {"scheduled": False, "reason": "fresh_audit", "age_hours": round(age, 2)}
        attempt_age = _hours_since(data.get("automatic_audit_last_attempt_at"))
        if attempt_age is not None and attempt_age < retry_hours:
            return {"scheduled": False, "reason": "retry_cooldown", "age_hours": round(attempt_age, 2)}
        _AUDIT_IN_FLIGHT = True
        data["automatic_audit_last_attempt_at"] = now_iso()
        data["automatic_audit_state"] = "running"
        data["automatic_audit_last_error"] = ""
        try:
            write_json(STORE, data)
        except Exception:
            _AUDIT_IN_FLIGHT = False
            raise

    def worker():
        global _AUDIT_IN_FLIGHT
        try:
            result = audit({"site": DEFAULT_SITE})
            report = _load()
            inaccessible = any(int(result.get(key) or 0) == 0 for key in
                               ("homepage_status", "robots_status", "sitemap_status"))
            report["automatic_audit_state"] = "degraded" if inaccessible else "completed"
            report["automatic_audit_last_completed_at"] = now_iso()
            report["automatic_audit_last_error"] = "public_http_unavailable" if inaccessible else ""
            write_json(STORE, report)
        except Exception as error:
            try:
                report = _load()
                report["automatic_audit_state"] = "failed"
                report["automatic_audit_last_completed_at"] = now_iso()
                report["automatic_audit_last_error"] = f"{type(error).__name__}: {error}"[:300]
                write_json(STORE, report)
            except Exception:
                pass
        finally:
            with _AUDIT_LOCK:
                _AUDIT_IN_FLIGHT = False

    try:
        threading.Thread(target=worker, daemon=True, name="kz-seo-public-audit").start()
    except Exception:
        with _AUDIT_LOCK:
            _AUDIT_IN_FLIGHT = False
        raise
    return {"scheduled": True, "reason": "seo_public_audit_started"}


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-Site-Audit/2.2"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(2 * 1024 * 1024)
            return {"url": response.geturl(), "status": response.status, "content_type": response.headers.get("Content-Type", ""), "body": body.decode("utf-8", "replace")}
    except urllib.error.HTTPError as error:
        return {"url": url, "status": error.code, "content_type": error.headers.get("Content-Type", ""), "body": "", "error": f"HTTP {error.code}"}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {"url": url, "status": 0, "content_type": "", "body": "", "error": f"{type(error).__name__}: {error}"[:300]}


def _visible_text(body):
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", str(body or ""), flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _sitemap_summary(body):
    summary = {"kind": "invalid", "urls": [], "lastmod_count": 0, "error": ""}
    try:
        root = ET.fromstring(str(body or ""))
    except (ET.ParseError, ValueError) as error:
        summary["error"] = str(error)[:200]
        return summary
    summary["kind"] = root.tag.rsplit("}", 1)[-1]
    for node in root.iter():
        name = node.tag.rsplit("}", 1)[-1]
        if name == "loc" and str(node.text or "").strip():
            summary["urls"].append(str(node.text).strip())
        elif name == "lastmod" and str(node.text or "").strip():
            summary["lastmod_count"] += 1
    return summary


def _schema_health(body):
    blocks = re.findall(
        r"<script\b[^>]*type\s*=\s*([\"'])application/ld\+json\1[^>]*>(.*?)</script>",
        str(body or ""),
        flags=re.I | re.S,
    )
    valid = 0
    template_urls = False
    for _quote, raw in blocks:
        if re.search(r"\{\{\s*https?://", raw, flags=re.I):
            template_urls = True
        try:
            value = json.loads(raw.strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(value, (dict, list)):
            valid += 1
    return {"blocks": len(blocks), "valid_blocks": valid, "template_urls": template_urls}


def audit(payload=None):
    payload = payload or {}
    site = str(payload.get("site") or DEFAULT_SITE).strip()
    parts = urlsplit(site)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("官网地址必须是有效的 http 或 https 地址")
    if not site.endswith("/"):
        site += "/"
    home = _fetch(site)
    robots = _fetch(urljoin(site, "/robots.txt"))
    sitemap = _fetch(urljoin(site, "/sitemap.xml"))
    text = home["body"]
    visible = _visible_text(text)
    root_map = _sitemap_summary(sitemap["body"]) if sitemap["status"] == 200 else {"kind": "missing", "urls": [], "lastmod_count": 0}
    managed_url = next((url for url in root_map.get("urls") or [] if url.rstrip("/").endswith("sitemap.xml") and "/seo/" in url), urljoin(site, "/seo/sitemap.xml"))
    managed = _fetch(managed_url)
    managed_map = _sitemap_summary(managed["body"]) if managed["status"] == 200 else {"kind": "missing", "urls": [], "lastmod_count": 0}
    hub_url = urljoin(site, "/seo/")
    hub = _fetch(hub_url)
    hub_schema = _schema_health(hub.get("body"))
    sample_url = next((url for url in managed_map.get("urls") or [] if not url.rstrip("/").endswith("sitemap.xml")), "")
    sample = _fetch(sample_url) if sample_url else {"status": 0, "body": ""}
    sample_schema = _schema_health(sample.get("body"))
    item = {
        "audited_at": now_iso(), "site": site, "homepage_status": home["status"],
        "robots_status": robots["status"], "sitemap_status": sitemap["status"],
        "has_title": bool(re.search(r"<title>\s*[^<]+", text, re.I)),
        "has_description": bool(re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'][^\"']+", text, re.I)),
        "has_structured_data": "application/ld+json" in text.lower(),
        "has_canonical": bool(re.search(r"<link[^>]+rel=[\"']canonical[\"']", text, re.I)),
        "has_open_graph": bool(re.search(r"<meta[^>]+property=[\"']og:title[\"']", text, re.I)),
        "internal_link_count": len(re.findall(r"<a\b[^>]+href=", text, re.I)),
        "visible_text_chars": len(visible),
        "is_js_shell": len(visible) < 300,
        "root_sitemap": {"kind": root_map.get("kind"), "url_count": len(root_map.get("urls") or []), "lastmod_count": root_map.get("lastmod_count") or 0},
        "managed_sitemap": {"url": managed_url, "status": managed.get("status"), "kind": managed_map.get("kind"), "url_count": len(managed_map.get("urls") or []), "lastmod_count": managed_map.get("lastmod_count") or 0},
        "managed_seo_hub": {
            "url": hub_url,
            "status": hub.get("status"),
            "visible_text_chars": len(_visible_text(hub.get("body"))),
            "has_canonical": bool(re.search(r"<link[^>]+rel=[\"']canonical[\"']", hub.get("body") or "", re.I)),
            "has_open_graph": bool(re.search(r"<meta[^>]+property=[\"']og:title[\"']", hub.get("body") or "", re.I)),
            "schema": hub_schema,
        },
        "sample_public_page": {"url": sample_url, "status": sample.get("status"), "visible_text_chars": len(_visible_text(sample.get("body"))), "schema": sample_schema},
    }
    blockers = []
    if home["status"] != 200:
        blockers.append("官网首页不可正常抓取")
    if robots["status"] != 200:
        blockers.append("robots.txt 尚未部署")
    if sitemap["status"] != 200:
        blockers.append("sitemap.xml 尚未部署")
    if home["status"] == 200 and not item["has_structured_data"]:
        blockers.append("缺少结构化数据")
    if home["status"] == 200 and not item["has_canonical"]:
        blockers.append("首页缺少 canonical 标准网址")
    if home["status"] == 200 and not item["has_open_graph"]:
        blockers.append("首页缺少 Open Graph 分享摘要")
    if home["status"] == 200 and item["is_js_shell"]:
        blockers.append("首页可抓取正文偏少，可能只有前端JS壳")
    if home["status"] == 200 and item["internal_link_count"] == 0:
        blockers.append("首页源码没有可抓取的普通内部链接")
    if root_map.get("kind") == "urlset" and any(url.rstrip("/").endswith("sitemap.xml") for url in root_map.get("urls") or []):
        blockers.append("主站点地图把子站点地图当作普通网页，应改为 sitemapindex")
    if managed.get("status") != 200:
        blockers.append("SEO子站点地图不可正常抓取")
    elif managed_map.get("kind") != "urlset":
        blockers.append("SEO子站点地图结构无效")
    elif (managed_map.get("urls") or []) and int(managed_map.get("lastmod_count") or 0) < len(managed_map.get("urls") or []):
        blockers.append("SEO子站点地图缺少逐页 lastmod 更新时间")
    if hub.get("status") != 200:
        blockers.append("SEO可抓取入口页不可正常访问")
    elif len(_visible_text(hub.get("body"))) < 500 or hub_schema.get("valid_blocks", 0) < 1:
        blockers.append("SEO可抓取入口页正文或结构化数据不足")
    if sample_url and sample.get("status") != 200:
        blockers.append("SEO样本页面不可正常抓取")
    if sample_schema.get("template_urls"):
        blockers.append("SEO页面结构化数据仍包含未替换的网址模板")
    if sample_url and len(_visible_text(sample.get("body"))) < 500:
        blockers.append("SEO样本页面正文偏薄，缺少可引用事实")
    item["blockers"] = blockers
    item["result"] = "ready" if not blockers else "needs_work"
    data = _load()
    data["audits"].insert(0, item)
    data["audits"] = data["audits"][:30]
    write_json(STORE, data)
    return item


def create_pack(payload):
    campaign_id = str(payload.get("campaign_id") or "").strip()
    data = content_factory._load()
    campaign = content_factory._by_id(data["campaigns"], campaign_id, "增长任务")
    slug = re.sub(r"[^a-z0-9-]+", "-", f"{campaign['id']}-{campaign['region']}-{campaign['service']}".lower()).strip("-")
    facts = [
        f"服务区域：{campaign['region']}", f"服务类别：{campaign['service']}",
        "用户提交需求后可等待多位师傅报价，并由用户选择师傅。",
        "涉及现场情况的最终报价，以师傅查看实际状态并经用户确认后为准。",
        "家电维修新用户券按实际小程序规则使用：满100减10、满200减20、满300减30、满400减40。",
    ]
    faq = [
        {"question": f"{campaign['region']}的{campaign['service']}怎么下单？", "answer": "通过卡嘴子小程序提交问题、区域和可联系时间，等待师傅报价。"},
        {"question": "报价由谁决定？", "answer": "平台师傅可以报价，用户根据报价和服务信息自行选择；现场情况变化时需再次确认。"},
        {"question": "多久会回复？", "answer": "当前运营目标是在客服工作时段尽量于10分钟内响应；实际到场时间需与用户和师傅确认。"},
    ]
    pack = {
        "id": f"SEARCH-{campaign['id']}", "campaign_id": campaign["id"], "created_at": now_iso(),
        "region": campaign["region"], "service": campaign["service"], "slug": slug,
        "page_title": f"{campaign['region']}{campaign['service']}｜卡嘴子本地服务",
        "description": f"卡嘴子为{campaign['region']}用户提供{campaign['service']}需求发布、师傅报价与用户自主选择服务。",
        "h1": campaign["title"], "facts": facts, "faq": faq,
        "short_answer": f"在{campaign['region']}需要{campaign['service']}时，可通过卡嘴子小程序提交需求，由附近师傅报价，用户自主选择。",
        "schema_types": ["LocalBusiness", "Service", "FAQPage"],
        "deployment_status": "待官网发布", "indexing_status": "未验证收录",
    }
    store = _load()
    store["packs"] = [item for item in store["packs"] if item.get("id") != pack["id"]]
    store["packs"].insert(0, pack)
    write_json(STORE, store)
    export = data_root() / "r8" / "search_exports" / f"{pack['id']}.json"
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    pack["export_path"] = str(export)
    return pack
