"""R8-18 truthful SEO result verification, performance and internal-link evidence.

This module never infers INDEXED/RANKED/AI visibility from publication or submission.
External stages advance only when an external provider returns auditable evidence.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from core.storage import now_iso, read_json, write_json
from core.seo_geo_growth import STAGE_INDEX, dashboard, record_asset_stage
from integrations.credential_vault import get_secret, put_secret
from integrations import search_engine_submitter

STORE = "r8_18/seo_quality_evidence.json"
SCHEMA = "kz.seo-quality-evidence.v1"
PAGESPEED_KEY_SECRET = "seo.pagespeed.api_key"
PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
URL_INSPECTION_ENDPOINT = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def _empty():
    return {
        "schema": SCHEMA,
        "updated_at": now_iso(),
        "performance": {"last_run_at": "", "items": [], "errors": []},
        "internal_links": {"last_run_at": "", "pages": 0, "links": 0, "orphans": [], "broken": [], "items": []},
        "result_verification": {"last_run_at": "", "items": [], "errors": [], "google_ready": False},
    }


def _load():
    data = read_json(STORE, _empty())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = _empty()
    for key, value in _empty().items():
        data.setdefault(key, deepcopy(value))
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _normalize_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, host, path, "", ""))


def _public_assets(limit: int = 100) -> list[dict]:
    snap = dashboard()
    rows = []
    for asset in snap.get("assets", []):
        url = str(asset.get("public_url") or "").strip()
        if url.startswith("https://"):
            rows.append(dict(asset))
        if len(rows) >= max(1, min(100, int(limit or 100))):
            break
    return rows


def _request_json(url: str, *, method="GET", payload=None, headers=None, timeout=20) -> tuple[int, dict]:
    body = None
    request_headers = {"User-Agent": "Kazuizhi-R8-18-SEO-Evidence/1.0", "Accept": "application/json"}
    request_headers.update(headers or {})
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json; charset=utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            raw = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            try:
                return status, json.loads(raw or "{}")
            except json.JSONDecodeError:
                return status, {"raw": raw[:4000]}
    except urllib.error.HTTPError as error:
        raw = error.read(256 * 1024).decode("utf-8", errors="replace") if hasattr(error, "read") else str(error)
        try:
            payload_out = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload_out = {"error": raw[:4000] or str(error)}
        return int(getattr(error, "code", 0) or 0), payload_out
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, {"error": str(error)}


def configure(payload: dict) -> dict:
    key = str(payload.get("pagespeed_api_key") or "").strip()
    if key:
        if len(key) > 2048:
            raise ValueError("PageSpeed API Key 长度异常")
        put_secret(PAGESPEED_KEY_SECRET, key)
    return status()


def _pagespeed_key() -> str:
    try:
        return str(get_secret(PAGESPEED_KEY_SECRET) or "").strip()
    except (OSError, RuntimeError, ValueError):
        return ""


def _metric(audits: dict, key: str):
    row = audits.get(key) if isinstance(audits, dict) else None
    if not isinstance(row, dict):
        return None
    value = row.get("numericValue")
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _run_pagespeed(url: str, strategy: str) -> dict:
    query = [("url", url), ("strategy", strategy), ("category", "performance")]
    key = _pagespeed_key()
    if key:
        query.append(("key", key))
    endpoint = PAGESPEED_ENDPOINT + "?" + urllib.parse.urlencode(query)
    status_code, payload = _request_json(endpoint, timeout=35)
    lighthouse = payload.get("lighthouseResult") if isinstance(payload, dict) else None
    categories = lighthouse.get("categories") if isinstance(lighthouse, dict) else {}
    performance = categories.get("performance") if isinstance(categories, dict) else {}
    audits = lighthouse.get("audits") if isinstance(lighthouse, dict) else {}
    score_raw = performance.get("score") if isinstance(performance, dict) else None
    score = None
    try:
        if score_raw is not None:
            score = round(float(score_raw) * 100)
    except (TypeError, ValueError):
        score = None
    ok = bool(200 <= status_code < 300 and score is not None)
    return {
        "ok": ok,
        "http_status": status_code,
        "url": url,
        "strategy": strategy,
        "performance_score": score,
        "lcp_ms": _metric(audits, "largest-contentful-paint"),
        "inp_ms": _metric(audits, "interaction-to-next-paint"),
        "tbt_ms": _metric(audits, "total-blocking-time"),
        "cls": _metric(audits, "cumulative-layout-shift"),
        "fcp_ms": _metric(audits, "first-contentful-paint"),
        "ttfb_ms": _metric(audits, "server-response-time"),
        "checked_at": now_iso(),
        "source": "Google PageSpeed Insights API v5",
        "error": "" if ok else str((payload.get("error") if isinstance(payload, dict) else payload) or "PageSpeed 未返回可用 Lighthouse performance 结果")[:1200],
        "api_key_configured": bool(key),
    }


def run_performance(limit: int = 3) -> dict:
    assets = _public_assets(limit=max(1, min(5, int(limit or 3))))
    data = _load()
    items = []
    errors = []
    for asset in assets:
        url = str(asset.get("public_url") or "")
        for strategy in ("mobile", "desktop"):
            row = _run_pagespeed(url, strategy)
            row["asset_id"] = asset.get("id")
            items.append(row)
            if not row.get("ok"):
                errors.append({"asset_id": asset.get("id"), "strategy": strategy, "error": row.get("error"), "http_status": row.get("http_status")})
    data["performance"] = {"last_run_at": now_iso(), "items": items[-20:], "errors": errors[-20:]}
    _save(data)
    good = [x for x in items if x.get("ok")]
    return {
        "ok": bool(good),
        "tested": len(items),
        "successful": len(good),
        "failed": len(items) - len(good),
        "items": items,
        "reason": "" if good else ("no_public_pages" if not assets else "pagespeed_no_successful_result"),
        "truth": "性能状态只来自 PageSpeed/Lighthouse 独立证据；HTTP 200 不会被当成性能通过。",
    }


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if str(tag).lower() != "a":
            return
        for key, value in attrs:
            if str(key).lower() == "href" and value:
                self.hrefs.append(str(value).strip())


def _fetch_html(url: str, timeout=12) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-18-Internal-Link-Auditor/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = int(getattr(response, "status", 200) or 200)
            body = response.read(1024 * 1024).decode("utf-8", errors="replace")
            return code, body
    except urllib.error.HTTPError as error:
        return int(getattr(error, "code", 0) or 0), ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, ""


def run_internal_links(limit: int = 100) -> dict:
    assets = _public_assets(limit=limit)
    known = {_normalize_url(x.get("public_url")): x for x in assets if _normalize_url(x.get("public_url"))}
    inbound = {url: 0 for url in known}
    page_rows = []
    broken: list[dict] = []
    total_links = 0
    site_host = ""
    if known:
        site_host = urlsplit(next(iter(known))).netloc.lower()
    for normalized, asset in known.items():
        code, html = _fetch_html(str(asset.get("public_url") or ""))
        parser = _LinkParser()
        if html:
            try:
                parser.feed(html)
            except (ValueError, TypeError):
                pass
        internal_targets = []
        for href in parser.hrefs:
            absolute = _normalize_url(urljoin(str(asset.get("public_url") or ""), href))
            parts = urlsplit(absolute)
            if parts.netloc.lower() != site_host:
                continue
            if not (parts.path or "/").startswith("/seo"):
                continue
            total_links += 1
            internal_targets.append(absolute)
            if absolute in inbound:
                inbound[absolute] += 1
            else:
                target_code, _ = _fetch_html(absolute, timeout=8)
                if not 200 <= target_code < 400:
                    broken.append({"from": normalized, "to": absolute, "http_status": target_code})
        page_rows.append({
            "asset_id": asset.get("id"),
            "url": normalized,
            "http_status": code,
            "outbound_managed_links": len(set(internal_targets)),
        })
    orphans = [url for url, count in inbound.items() if count == 0]
    for row in page_rows:
        row["inbound_managed_links"] = inbound.get(row["url"], 0)
        row["orphan"] = row["url"] in orphans
    data = _load()
    data["internal_links"] = {
        "last_run_at": now_iso(),
        "pages": len(known),
        "links": total_links,
        "orphans": orphans,
        "broken": broken[:100],
        "items": page_rows[:100],
    }
    _save(data)
    return {
        "ok": bool(known),
        "pages": len(known),
        "links": total_links,
        "orphan_count": len(orphans),
        "broken_count": len(broken),
        "orphans": orphans,
        "broken": broken[:100],
        "items": page_rows,
        "truth": "内链审计只统计真实公开页面中的可抓取 <a href> 链接；不会用 sitemap 或页面生成事实伪造入链。",
    }


def _google_credentials():
    try:
        account = search_engine_submitter._connected_account("google_search_console")
        token = search_engine_submitter._google_access_token(account)
        return account, str(token or "").strip()
    except (OSError, RuntimeError, ValueError, TypeError, KeyError):
        return None, ""


def _inspect_google(url: str, site_url: str, token: str) -> dict:
    code, payload = _request_json(
        URL_INSPECTION_ENDPOINT,
        method="POST",
        payload={"inspectionUrl": url, "siteUrl": site_url, "languageCode": "zh-CN"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=25,
    )
    result = payload.get("inspectionResult") if isinstance(payload, dict) else None
    index = result.get("indexStatusResult") if isinstance(result, dict) else None
    if not isinstance(index, dict):
        return {"ok": False, "http_status": code, "url": url, "error": str(payload.get("error") if isinstance(payload, dict) else payload)[:1200]}
    coverage = str(index.get("coverageState") or "")
    verdict = str(index.get("verdict") or "")
    last_crawl = str(index.get("lastCrawlTime") or "")
    indexed = bool(verdict.upper() == "PASS" and "indexed" in coverage.lower())
    return {
        "ok": 200 <= code < 300,
        "http_status": code,
        "url": url,
        "verdict": verdict,
        "coverage_state": coverage,
        "robots_txt_state": index.get("robotsTxtState"),
        "indexing_state": index.get("indexingState"),
        "page_fetch_state": index.get("pageFetchState"),
        "last_crawl_time": last_crawl,
        "crawled": bool(last_crawl),
        "indexed": indexed,
        "source": "Google Search Console URL Inspection API",
        "checked_at": now_iso(),
    }


def _search_analytics(url: str, site_url: str, token: str) -> dict:
    encoded_site = urllib.parse.quote(site_url, safe="")
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{encoded_site}/searchAnalytics/query"
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=27)
    code, payload = _request_json(
        endpoint,
        method="POST",
        payload={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query", "page"],
            "dimensionFilterGroups": [{"filters": [{"dimension": "page", "operator": "equals", "expression": url}]}],
            "rowLimit": 10,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=25,
    )
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {"ok": False, "http_status": code, "rows": [], "error": str(payload.get("error") if isinstance(payload, dict) else payload)[:1200]}
    clean = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        position = row.get("position")
        try:
            position = float(position)
        except (TypeError, ValueError):
            continue
        clean.append({
            "query": str((row.get("keys") or [""])[0] or ""),
            "page": str((row.get("keys") or ["", url])[1] if len(row.get("keys") or []) > 1 else url),
            "position": round(position, 2),
            "clicks": int(row.get("clicks") or 0),
            "impressions": int(row.get("impressions") or 0),
            "ctr": row.get("ctr"),
        })
    return {"ok": 200 <= code < 300, "http_status": code, "rows": clean, "source": "Google Search Console Search Analytics API", "checked_at": now_iso()}


def _maybe_advance(asset: dict, stage: str, evidence: dict) -> bool:
    current = str(asset.get("stage") or "DISCOVERED")
    if STAGE_INDEX.get(current, 0) >= STAGE_INDEX.get(stage, 0):
        return False
    record_asset_stage(str(asset.get("id") or ""), stage, evidence)
    asset["stage"] = stage
    return True


def run_result_verification(limit: int = 10) -> dict:
    assets = _public_assets(limit=max(1, min(50, int(limit or 10))))
    account, token = _google_credentials()
    snap = dashboard()
    site_url = str(snap.get("config", {}).get("site_base_url") or "https://kazuizhi.com/").rstrip("/") + "/"
    data = _load()
    items = []
    errors = []
    crawled = indexed = ranked = 0
    if not token:
        result = {
            "last_run_at": now_iso(),
            "items": [],
            "errors": [{"reason": "google_search_console_not_authorized", "message": "Google Search Console 尚未完成真实站点验证/OAuth 授权；不会把已提交误记为抓取或收录。"}],
            "google_ready": False,
        }
        data["result_verification"] = result
        _save(data)
        return {"ok": False, "skipped": True, "reason": "google_search_console_not_authorized", **result}

    for asset in assets:
        asset_id = str(asset.get("id") or "")
        url = str(asset.get("public_url") or "")
        inspection = _inspect_google(url, site_url, token)
        analytics = _search_analytics(url, site_url, token)
        row = {"asset_id": asset_id, "url": url, "inspection": inspection, "search_analytics": analytics}
        if not inspection.get("ok"):
            errors.append({"asset_id": asset_id, "source": "url_inspection", "error": inspection.get("error"), "http_status": inspection.get("http_status")})
        else:
            if inspection.get("crawled"):
                crawled += 1
                _maybe_advance(asset, "CRAWLED", {"crawl_evidence": inspection})
            if inspection.get("indexed"):
                indexed += 1
                if STAGE_INDEX.get(str(asset.get("stage") or "DISCOVERED"), 0) < STAGE_INDEX["CRAWLED"]:
                    _maybe_advance(asset, "CRAWLED", {"crawl_evidence": inspection})
                _maybe_advance(asset, "INDEXED", {"index_evidence": inspection})
        analytics_rows = analytics.get("rows") if isinstance(analytics, dict) else []
        if analytics.get("ok") and analytics_rows:
            best = min((r for r in analytics_rows if float(r.get("position") or 0) > 0), key=lambda x: float(x.get("position") or math.inf), default=None)
            if best:
                ranked += 1
                if STAGE_INDEX.get(str(asset.get("stage") or "DISCOVERED"), 0) >= STAGE_INDEX["INDEXED"]:
                    _maybe_advance(asset, "RANKED", {"engine": "google_search_console", "rank": max(1, int(math.ceil(float(best["position"])))), "keyword": best.get("query") or asset.get("keyword")})
                row["ranking_evidence"] = best
        elif not analytics.get("ok"):
            errors.append({"asset_id": asset_id, "source": "search_analytics", "error": analytics.get("error"), "http_status": analytics.get("http_status")})
        items.append(row)

    result = {"last_run_at": now_iso(), "items": items[-50:], "errors": errors[-50:], "google_ready": True}
    data["result_verification"] = result
    _save(data)
    return {
        "ok": True,
        "skipped": False,
        "checked": len(items),
        "crawled_evidence": crawled,
        "indexed_evidence": indexed,
        "ranking_evidence": ranked,
        "geo_observations": int(snap.get("geo", {}).get("observations") or 0),
        "items": items,
        "errors": errors,
        "truth": "提交回执不会自动变成抓取/收录/排名。CRAWLED/INDEXED/RANKED 只在 Google Search Console 返回对应真实证据后推进；AI/GEO 仍需独立外部观察证据。",
    }


def status() -> dict:
    data = _load()
    account, token = _google_credentials()
    performance = deepcopy(data.get("performance") or {})
    internal = deepcopy(data.get("internal_links") or {})
    verify = deepcopy(data.get("result_verification") or {})
    mobile_scores = [x.get("performance_score") for x in performance.get("items", []) if x.get("ok") and x.get("strategy") == "mobile" and x.get("performance_score") is not None]
    desktop_scores = [x.get("performance_score") for x in performance.get("items", []) if x.get("ok") and x.get("strategy") == "desktop" and x.get("performance_score") is not None]
    return {
        "google": {
            "oauth_ready": bool(account and token),
            "reason": "" if account and token else "等待 Google Search Console 完成站点所有权验证并完成 OAuth 授权",
        },
        "result_verification": verify,
        "performance": {
            **performance,
            "api_key_configured": bool(_pagespeed_key()),
            "mobile_score": round(sum(mobile_scores) / len(mobile_scores), 1) if mobile_scores else None,
            "desktop_score": round(sum(desktop_scores) / len(desktop_scores), 1) if desktop_scores else None,
            "ready": bool(performance.get("items")),
        },
        "internal_links": {
            **internal,
            "ready": bool(internal.get("last_run_at")),
        },
        "truth": "结果验证、性能与内链三类证据彼此独立；未取得外部证据时保持等待，不用 0 伪装为已验证结果。",
    }


def run_all(limit: int = 10) -> dict:
    return {
        "result_verification": run_result_verification(limit=limit),
        "performance": run_performance(limit=min(3, limit)),
        "internal_links": run_internal_links(limit=max(10, limit)),
        "status": status(),
    }
