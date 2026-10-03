from pathlib import Path
import importlib
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
BACKEND = SRC / "backend" / "server.py"
UI = SRC / "web" / "seo-geo-connector-matrix.js"
BUILD_INFO = SRC / "web" / "build_info.js"
RUNTIME = SRC / "backend" / "runtime.py"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    old_relay = {
        "KAZUIZHI_CHATGPT_RELAY_URL": os.environ.get("KAZUIZHI_CHATGPT_RELAY_URL"),
        "KAZUIZHI_CHATGPT_RELAY_TOKEN": os.environ.get("KAZUIZHI_CHATGPT_RELAY_TOKEN"),
        "KAZUIZHI_CHATGPT_RELAY_ENABLED": os.environ.get("KAZUIZHI_CHATGPT_RELAY_ENABLED"),
    }
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["LOCALAPPDATA"] = td
            os.environ.pop("KAZUIZHI_CHATGPT_RELAY_URL", None)
            os.environ.pop("KAZUIZHI_CHATGPT_RELAY_TOKEN", None)
            os.environ.pop("KAZUIZHI_CHATGPT_RELAY_ENABLED", None)
            sys.path.insert(0, str(SRC))

            from integrations import seo_geo_connector_router_v2 as router
            from integrations import seo_public_deployer
            from integrations import chatgpt_relay_agent
            from backend import runtime

            importlib.reload(chatgpt_relay_agent)
            importlib.reload(router)
            importlib.reload(seo_public_deployer)
            importlib.reload(runtime)

            matrix = router.route_matrix()
            assert matrix["total_connectors"] >= 20
            assert matrix["routable_connectors"] >= 1
            assert matrix["seo_routes"] >= 1
            assert matrix["geo_routes"] >= 1
            assert matrix["distribution_routes"] >= 1
            assert matrix["ai_execution_routes"] >= 1
            assert "routes" in matrix and matrix["routes"]
            assert all("route_status" in item for item in matrix["routes"])
            assert all("capability_domains" in item for item in matrix["routes"])

            summary = router.controller_routes()
            assert "seo" in summary and "geo" in summary
            assert "distribution" in summary and "ai_execution" in summary
            assert isinstance(summary["seo"], list)
            assert isinstance(summary["geo"], list)

            relay = chatgpt_relay_agent.relay_status()
            assert relay["enabled"] is False
            assert relay["configured"] is False
            assert relay["live"] is False
            assert relay["status"] in {"disabled", "unconfigured", "offline"}

            health = runtime.runtime_health()
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
            supported = ('R8-21', 'R8-22', 'R8-23', 'R8-23.3 Candidate', 'R8-23.4 Candidate')
            assert any(f'phase: "{phase}"' in build for phase in supported)
            assert any(label in build for label in (
                "SEO/GEO Unified Connectors", "Autonomous Convergence", "Autonomous Growth OS",
                "Runtime Execution & UI Convergence", "Runtime & Route Recovery",
            ))
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
