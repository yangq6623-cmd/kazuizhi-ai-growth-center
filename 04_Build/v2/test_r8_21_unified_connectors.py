"""Offline release gate for R8-21 unified SEO/GEO connector routing."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
BACKEND = SRC / "backend" / "r8_20_seo_geo_growth_patch.py"
UI = SRC / "web" / "seo-geo-connector-matrix.js"
BUILD_INFO = SRC / "web" / "build_info.js"
RUNTIME = SRC / "core" / "runtime_resilience.py"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    relay_keys = (
        "KAZUIZHI_CHATGPT_RELAY_URL",
        "KAZUIZHI_CHATGPT_CONNECTOR_ID",
        "KAZUIZHI_CHATGPT_RELAY_SECRET",
    )
    old_relay = {key: os.environ.get(key) for key in relay_keys}
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        for key in relay_keys:
            os.environ.pop(key, None)
        sys.path.insert(0, str(SRC))
        try:
            from integrations import channel_registry
            from integrations import seo_geo_connector_router_v2 as router
            from core import runtime_resilience

            registry = channel_registry.snapshot()
            channel_ids = {row.get("id") for row in registry.get("channels") or []}
            expected_channels = {
                "douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo",
                "baidu_search", "wechat_search", "sogou_search", "360_search",
                "maps_local", "local_life", "qa", "forum", "website", "mini_program",
            }
            assert expected_channels <= channel_ids, channel_ids

            matrix = router.snapshot(check_live=False)
            assert matrix["schema"] == "kz.seo-geo-connector-router.v2"
            rows = {row["id"]: row for row in matrix["connectors"]}
            assert expected_channels <= set(rows), set(rows)

            for connector_id in (
                "baidu_search_resource_api", "bing_indexnow", "google_search_console",
                "seo_public_deployer", "remote_agent", "model_cloud", "model_local",
                "chatgpt_control", "chatgpt_relay", "geo_external_ai_browser",
            ):
                assert connector_id in rows, connector_id

            assert rows["bing_indexnow"]["use_for_seo"] is True
            assert rows["google_search_console"]["use_for_seo"] is True
            assert rows["seo_public_deployer"]["use_for_geo"] is True
            assert rows["model_cloud"]["formal_geo_evidence"] is False
            assert rows["model_local"]["formal_geo_evidence"] is False
            for social in ("douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo"):
                assert rows[social]["use_for_distribution"] is True
                assert rows[social]["formal_geo_evidence"] is False

            formal = rows["geo_external_ai_browser"]
            assert formal["software_route_ready"] is True
            assert formal["formal_geo_evidence"] is True
            assert "Evidence" in formal["formal_evidence_policy"]
            assert matrix["summary"]["formal_geo_routes"] >= 1

            # Missing Relay config is a truthful blocker.
            relay = rows["chatgpt_relay"]
            assert relay["software_route_ready"] is False
            assert relay["route_state"] == "not_configured"
            assert "Relay" in relay["name"]

            # Configuration alone still is not a live Command -> Receipt route.
            os.environ["KAZUIZHI_CHATGPT_RELAY_URL"] = "http://127.0.0.1:65530"
            os.environ["KAZUIZHI_CHATGPT_CONNECTOR_ID"] = "ci-connector"
            os.environ["KAZUIZHI_CHATGPT_RELAY_SECRET"] = "x" * 40
            configured_matrix = router.snapshot(check_live=False)
            configured_relay = next(row for row in configured_matrix["connectors"] if row["id"] == "chatgpt_relay")
            assert configured_relay["software_route_ready"] is True
            assert configured_relay["external_verified"] is False
            assert configured_relay["route_state"] == "configured_waiting_live"
            for key in relay_keys:
                os.environ.pop(key, None)

            controller = router.route_summary_for_controller(check_live=False)
            assert "bing_indexnow" in controller["seo"]
            assert "geo_external_ai_browser" in controller["formal_geo"]
            assert controller["live_remote_control"] == []
            assert any(x.get("id") == "chatgpt_relay" for x in controller["blockers"])

            runtime_resilience.start_process(keep_awake=True)
            runtime_resilience.heartbeat("http_server", ok=True, detail="port=8876", force_persist=True)
            old_stamp = (datetime.now().astimezone() - timedelta(hours=2)).isoformat()
            runtime_resilience._STATE["workers"]["http_server"]["last_heartbeat_at"] = old_stamp
            health = runtime_resilience.snapshot(stale_after_seconds=1)
            assert health["workers"]["http_server"]["state"] == "healthy"
            assert health["workers"]["http_server"]["blocking_main_loop"] is True
            assert "http_server" not in health["unhealthy_workers"]

            backend = BACKEND.read_text(encoding="utf-8")
            for marker in (
                "seo_geo_connector_router_v2", "seo-geo-connector-matrix.js",
                "/api/r8-21/seo-geo/connectors", "/api/r8-21/seo-geo/controller-routes",
                "r8_21_full_autonomous_loop_with_unified_connectors",
            ):
                assert marker in backend, marker

            ui = UI.read_text(encoding="utf-8")
            for marker in (
                "SEO / GEO 统一连接路由矩阵", "软件可路由", "外部已验证", "SEO路由", "GEO路由",
                "同步并检查服务器通道", "ChatGPT 安全 Relay", "模型/API普通输出",
            ):
                assert marker in ui, marker

            build = BUILD_INFO.read_text(encoding="utf-8")
            assert ('phase: "R8-21"' in build) or ('phase: "R8-22"' in build)
            assert ("SEO/GEO Unified Connectors" in build) or ("Autonomous Convergence" in build)
            assert "blocking_main_loop" in RUNTIME.read_text(encoding="utf-8")

            print("PASS: R8-21 unified connection center -> SEO/GEO capability routes + truth gates + runtime health fix")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            for key, value in old_relay.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    main()
