"""Regression gate for truthful R8-18 SEO evidence/performance/internal-link work."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-r818-") as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            from integrations import seo_quality_evidence as quality

            require(quality._normalize_url("HTTPS://KAZUIZHI.COM/seo/demo/?x=1#x") == "https://kazuizhi.com/seo/demo", "URL normalization regressed")

            assets = [
                {"id": "A", "public_url": "https://kazuizhi.com/seo/a.html"},
                {"id": "B", "public_url": "https://kazuizhi.com/seo/b.html"},
                {"id": "C", "public_url": "https://kazuizhi.com/seo/c.html"},
            ]
            quality._public_assets = lambda limit=100: assets[:limit]
            html = {
                "https://kazuizhi.com/seo/a.html": '<a href="/seo/b.html">B</a>',
                "https://kazuizhi.com/seo/b.html": '<a href="/seo/a.html">A</a>',
                "https://kazuizhi.com/seo/c.html": '<p>no managed links</p>',
            }
            quality._fetch_html = lambda url, timeout=12: (200, html.get(url, ""))
            links = quality.run_internal_links(limit=10)
            require(links["ok"], "internal-link audit did not run")
            require(links["pages"] == 3, "internal-link page count changed")
            require(links["orphan_count"] == 1 and links["orphans"] == ["https://kazuizhi.com/seo/c.html"], "orphan evidence changed")
            require(links["broken_count"] == 0, "valid managed links were reported broken")

            quality._run_pagespeed = lambda url, strategy: {
                "ok": True, "url": url, "strategy": strategy,
                "performance_score": 88 if strategy == "mobile" else 96,
                "checked_at": "now", "source": "test",
            }
            perf = quality.run_performance(limit=1)
            require(perf["ok"] and perf["successful"] == 2, "performance evidence aggregation regressed")
            snap = quality.status()
            require(snap["performance"]["mobile_score"] == 88, "mobile PageSpeed score missing")
            require(snap["performance"]["desktop_score"] == 96, "desktop PageSpeed score missing")

            quality._google_credentials = lambda: (None, "")
            skipped = quality.run_result_verification(limit=10)
            require(skipped["skipped"] and skipped["reason"] == "google_search_console_not_authorized", "Google evidence gate must stay closed without OAuth")

            ui = SOURCE / "web" / "r8_18_seo_quality_ui.js"
            require(ui.is_file(), "R8-18 SEO quality UI missing")
            text = ui.read_text(encoding="utf-8")
            for marker in ("验证真实结果", "运行 PageSpeed", "审计内链", "/api/r8-18/seo-quality/verify-results"):
                require(marker in text, f"UI control marker missing: {marker}")

            print("R8-18 SEO quality evidence gate: PASS")
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
