#!/usr/bin/env python3
"""#816 SEO-only deterministic acceptance: no public calls and no GEO writes."""
import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(ROOT))
from promotion import search_growth as site

class SeoAuditIsolation(unittest.TestCase):
    def test_network_failure_is_reported_not_raised(self):
        with patch.object(site.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")):
            result = site._fetch("https://kazuizhi.example/")
        self.assertEqual(result["status"], 0)
        self.assertIn("URLError", result["error"])

    def test_inaccessible_site_is_not_misdiagnosed_as_missing_meta_tags(self):
        def offline(url):
            return {"url": url, "status": 0, "content_type": "", "body": "", "error": "offline"}
        with patch.object(site, "_fetch", side_effect=offline), patch.object(site, "_load", return_value={"audits":[],"packs":[]}), patch.object(site, "write_json"):
            report = site.audit()
        self.assertIn("官网首页不可正常抓取", report["blockers"])
        self.assertNotIn("缺少结构化数据", report["blockers"])
        self.assertNotIn("首页可抓取正文偏少，可能只有前端JS壳", report["blockers"])

    def test_exact_seven_historical_checks_are_supported(self):
        base="https://kazuizhi.com/"
        long_html='<html><body>'+('涟水县专业维修服务 '*100)+'</body></html>'
        schema='<script type="application/ld+json">{"@context":"https://schema.org","@type":"Service"}</script>'
        def source(url):
            if url == base:
                body='<html><title>卡嘴子</title><meta name="description" content="卡嘴子本地服务"><body>卡嘴子</body></html>'
            elif url.endswith("/robots.txt"):
                body="User-agent: *\\nAllow: /"
            elif url.endswith("/sitemap.xml") and "/seo/" not in url:
                body='<urlset><url><loc>https://kazuizhi.com/seo/sitemap.xml</loc></url></urlset>'
            elif url.endswith("/seo/sitemap.xml"):
                body='<urlset><url><loc>https://kazuizhi.com/seo/example/</loc></url></urlset>'
            elif url.endswith("/seo/"):
                body=long_html+schema
            else:
                body=long_html+schema
            return {"url":url,"status":200,"body":body,"content_type":"text/html"}
        with patch.object(site, "_fetch", side_effect=source),patch.object(site, "_load",return_value={"audits":[],"packs":[]}),patch.object(site,"write_json"):
            report=site.audit()
        self.assertEqual(len(report["blockers"]),7,report["blockers"])
        self.assertEqual(report["root_sitemap"]["kind"],"urlset")
        self.assertEqual(report["managed_sitemap"]["lastmod_count"],0)

    def test_scheduler_tracks_new_attempt_without_blocking(self):
        shared={"audits":[],"packs":[]}
        def load():return dict(shared)
        def save(_path,value):shared.clear();shared.update(value)
        class ImmediateThread:
            def __init__(self,target,**_):self.target=target
            def start(self):self.target()
        with patch.object(site,"_load",side_effect=load),patch.object(site,"write_json",side_effect=save),patch.object(site,"audit",return_value={"homepage_status":200,"robots_status":200,"sitemap_status":200}),patch.object(site.threading,"Thread",ImmediateThread):
            first=site.schedule_automatic_audit()
            second=site.schedule_automatic_audit()
        self.assertTrue(first["scheduled"])
        self.assertEqual(second["reason"],"retry_cooldown")
        self.assertEqual(shared["automatic_audit_state"],"completed")

if __name__ == "__main__":
    unittest.main(verbosity=2)
