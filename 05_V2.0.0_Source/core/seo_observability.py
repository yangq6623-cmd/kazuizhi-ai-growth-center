"""Bounded, evidence-first public SEO technical observations.

This module intentionally measures only what a local desktop process can
actually observe: public HTTP response timing and crawlable same-site links.
It does not manufacture Lighthouse, Core Web Vitals, crawl, or index results.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from statistics import median
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from core.storage import now_iso, read_json, write_json


STORE = "r8_17/seo_observability.json"
SCHEMA = "kz.seo-observability.v1"
MAX_PAGES = 20
MAX_BODY_BYTES = 512 * 1024


def _default():
    return {
        "schema": SCHEMA,
        "checked_at": "",
        "state": "not_started",
        "target_count": 0,
        "network": {},
        "links": {},
        "pages": [],
        "truth": "尚未执行公网网络响应与内链检查。",
    }


def _load():
    data = read_json(STORE, _default())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = _default()
    for key, value in _default().items():
        data.setdefault(key, value)
    return data


def status():
    """Return the latest persisted observation without triggering network I/O."""
    return _load()


def should_run_today():
    return not str(_load().get("checked_at") or "").startswith(now_iso()[:10])


def _normal_url(value):
    parts = urlsplit(str(value or "").strip())
    if parts.scheme != "https" or not parts.netloc:
        return ""
    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, parts.query, ""))


def _origin(value):
    parts = urlsplit(value)
    return parts.scheme, parts.netloc.lower()


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def _read_page(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-17-SEO-Audit/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read(MAX_BODY_BYTES)
            return {
                "url": response.geturl(),
                "status": int(getattr(response, "status", 200) or 200),
                "content_type": response.headers.get("Content-Type", ""),
                "bytes": len(body),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
                "body": body.decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as error:
        return {
            "url": url, "status": int(error.code), "content_type": error.headers.get("Content-Type", ""),
            "bytes": 0, "elapsed_ms": round((time.perf_counter() - started) * 1000), "body": "",
            "error": f"HTTP {error.code}",
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {
            "url": url, "status": 0, "content_type": "", "bytes": 0,
            "elapsed_ms": round((time.perf_counter() - started) * 1000), "body": "",
            "error": type(error).__name__,
        }


def run(snapshot):
    """Inspect verified public asset URLs in a bounded, same-origin read-only pass."""
    assets = list((snapshot or {}).get("assets") or [])
    config = (snapshot or {}).get("config") or {}
    expected_origin = _origin(_normal_url(config.get("site_base_url")))
    targets = []
    for asset in assets:
        url = _normal_url(asset.get("public_url"))
        if url and _origin(url) == expected_origin and url not in targets:
            targets.append(url)
    targets = targets[:MAX_PAGES]
    if not expected_origin or not targets:
        result = _default()
        result.update({
            "checked_at": now_iso(), "state": "waiting_for_verified_public_pages", "target_count": len(targets),
            "truth": "尚无同一 HTTPS 官网来源的已验证公开页面，未执行网络响应或内链检查。",
        })
        write_json(STORE, result)
        return result

    target_keys = {_normal_url(url).rstrip("/") or "/" for url in targets}
    incoming = {key: 0 for key in target_keys}
    rows, timings = [], []
    for url in targets:
        fetched = _read_page(url)
        status = int(fetched.get("status") or 0)
        html = fetched.pop("body", "")
        hrefs = []
        if 200 <= status < 300 and "html" in str(fetched.get("content_type") or "").lower():
            parser = _Links()
            try:
                parser.feed(html)
            except ValueError:
                pass
            for href in parser.hrefs:
                absolute = _normal_url(urldefrag(urljoin(url, href))[0])
                if absolute and _origin(absolute) == expected_origin:
                    hrefs.append(absolute)
                    key = absolute.rstrip("/") or "/"
                    if key in incoming:
                        incoming[key] += 1
        elapsed = int(fetched.get("elapsed_ms") or 0)
        if status:
            timings.append(elapsed)
        rows.append({
            "url": url, "status": status, "elapsed_ms": elapsed, "bytes": int(fetched.get("bytes") or 0),
            "internal_links": len(hrefs), "error": fetched.get("error", ""),
        })

    reachable = [row for row in rows if 200 <= row["status"] < 300]
    linkable = [row for row in reachable if row["internal_links"] > 0]
    result = {
        "schema": SCHEMA,
        "checked_at": now_iso(),
        "state": "measured" if reachable else "unavailable",
        "target_count": len(targets),
        "network": {
            "reachable_pages": len(reachable),
            "failed_pages": len(rows) - len(reachable),
            "median_response_ms": int(median(timings)) if timings else None,
            "slow_pages_over_3000ms": sum(1 for value in timings if value > 3000),
            "measurement": "公网 HTTP 响应时间与响应体大小；不是 Lighthouse、Core Web Vitals 或移动端体验分数。",
        },
        "links": {
            "total_internal_links": sum(row["internal_links"] for row in reachable),
            "pages_with_outbound_internal_links": len(linkable),
            "pages_without_outbound_internal_links": len(reachable) - len(linkable),
            "orphan_candidates": sum(1 for key in target_keys if incoming.get(key, 0) == 0),
            "measurement": "只统计本次已验证公开页之间及同站可抓取链接；候选孤儿页需要结合全站 sitemap 后人工确认。",
        },
        "pages": rows,
        "truth": "本次结果来自公开 HTTPS 页面实际响应与 HTML 链接扫描；不代表搜索引擎已抓取、已收录或有排名。",
    }
    write_json(STORE, result)
    return result
