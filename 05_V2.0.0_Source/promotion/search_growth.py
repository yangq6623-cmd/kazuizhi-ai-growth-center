"""Truthful local SEO/GEO audit and reusable answer-pack generation."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core.storage import data_root, now_iso, read_json, write_json
from promotion import content_factory


STORE = "r8/search_growth.json"
DEFAULT_SITE = "https://kazuizhi.com/"


def _load():
    data = read_json(STORE, {"audits": [], "packs": []})
    if not isinstance(data, dict):
        data = {"audits": [], "packs": []}
    data.setdefault("audits", [])
    data.setdefault("packs", [])
    return data


def status():
    data = _load()
    return {
        "status": "available", "site": DEFAULT_SITE,
        "latest_audit": data["audits"][0] if data["audits"] else None,
        "packs": data["packs"][:30],
        "truth_rule": "收录、排名和AI引用只记录实际观察结果；生成内容包不等于已经部署或收录。",
    }


def _fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-Site-Audit/2.2"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(2 * 1024 * 1024)
            return {"url": response.geturl(), "status": response.status, "content_type": response.headers.get("Content-Type", ""), "body": body.decode("utf-8", "replace")}
    except urllib.error.HTTPError as error:
        return {"url": url, "status": error.code, "content_type": error.headers.get("Content-Type", ""), "body": ""}


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
    item = {
        "audited_at": now_iso(), "site": site, "homepage_status": home["status"],
        "robots_status": robots["status"], "sitemap_status": sitemap["status"],
        "has_title": bool(re.search(r"<title>\s*[^<]+", text, re.I)),
        "has_description": bool(re.search(r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"'][^\"']+", text, re.I)),
        "has_structured_data": "application/ld+json" in text.lower(),
        "is_js_shell": len(re.sub(r"<[^>]+>", " ", text).strip()) < 300,
    }
    blockers = []
    if home["status"] != 200:
        blockers.append("官网首页不可正常抓取")
    if robots["status"] != 200:
        blockers.append("robots.txt 尚未部署")
    if sitemap["status"] != 200:
        blockers.append("sitemap.xml 尚未部署")
    if not item["has_structured_data"]:
        blockers.append("缺少结构化数据")
    if item["is_js_shell"]:
        blockers.append("首页可抓取正文偏少，可能只有前端JS壳")
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
