"""Offline release gate for R8-23.4 runtime/route recovery."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
PATCH = SRC / "backend" / "r8_23_4_runtime_route_recovery_patch.py"
UI = SRC / "web" / "r8_23_4_recovery.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from backend import r8_23_4_runtime_route_recovery_patch as recovery
            from core import seo_geo_growth_intelligence as growth

            version = recovery._version_payload()
            assert version["phase"] == "R8-23.4 Runtime & Route Recovery"
            assert version["alive"] is True
            assert version["api_contract"] == "r8-23.4"

            naive = recovery._aware_datetime("2026-10-03T12:00:00")
            assert naive is not None and naive.tzinfo is not None
            aware = recovery._aware_datetime("2026-10-03T12:00:00+08:00")
            assert aware is not None and aware.tzinfo is not None

            original_load = growth._load
            try:
                today = datetime.now().astimezone().date().isoformat()
                growth._load = lambda: {
                    "search_observations": [
                        {"observed_at": f"{today}T12:00:00", "kind": "impressions", "asset_id": "A", "url": "", "engine": "bing", "keyword": "涟水维修", "value": 10},
                        {"observed_at": f"{today}T12:01:00", "kind": "clicks", "asset_id": "A", "url": "", "engine": "bing", "keyword": "涟水维修", "value": 2},
                    ],
                    "attribution_events": [
                        {"at": f"{today}T12:02:00", "stage": "order", "source_tracking_id": "SRC-1"},
                    ],
                }
                search = recovery._safe_search_rollup(30)
                assert search["impressions"] == 10 and search["clicks"] == 2
                funnel = recovery._safe_attribution_funnel(30)
                assert funnel["order"] == 1
            finally:
                growth._load = original_load

            patch = PATCH.read_text(encoding="utf-8")
            ui = UI.read_text(encoding="utf-8")
            truth = TRUTH_PATCH.read_text(encoding="utf-8")

            for marker in (
                "/api/ping", "/api/version", "/api/r8-20/seo-geo",
                "r8_13_seo_geo_bridge.js", "r8_23_4_recovery.js",
                "R8-23.4 Runtime & Route Recovery", "formal GEO",
            ):
                assert marker in patch, marker
            assert '"r8_23_3_candidate.js"' not in patch.split("def _serve_autonomous_ops", 1)[1].split("def install", 1)[0]
            for marker in (
                "内容生产与发布", "r813-seo-geo", "SEO/GEO增长",
                "REQUEST_TIMEOUT_MS", "AbortController", "inflight",
                "后台检查可重试，不阻断界面查看", "clearLegacyBuildQuery",
            ):
                assert marker in ui, marker
            assert "BOOT_MAX_WAIT_MS" not in ui
            assert "r8_23_4_runtime_route_recovery_patch" in truth

            print("PASS: R8-23.4 restores fail-open startup, explicit content vs SEO/GEO routes, bounded requests and legacy-time-safe SEO/GEO status without weakening truth gates")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
