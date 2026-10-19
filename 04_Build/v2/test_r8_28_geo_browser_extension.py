"""Release gate for the R8-28 persistent domestic GEO Chrome executor."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
EXT = SOURCE / "browser_extension" / "kazuizhi_geo"


def main():
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "service-worker.js"
    assert {"alarms", "storage", "tabs", "scripting"}.issubset(manifest["permissions"])
    hosts = "\n".join(manifest["host_permissions"])
    for host in ("127.0.0.1:8876", "doubao.com", "douyin.com", "deepseek.com", "aliyun.com", "www.tongyi.com", "n.cn"):
        assert host in hosts, host

    worker = (EXT / "service-worker.js").read_text(encoding="utf-8")
    content = (EXT / "content-agent.js").read_text(encoding="utf-8")
    platforms = {"doubao_web", "douyin_search_web", "deepseek_web", "qwen_web", "so360_ai_search"}
    for platform in platforms:
        assert platform in worker
    for endpoint in ("register", "heartbeat", "claim", "receipt", "block"):
        assert f'call("{endpoint}"' in worker
    assert "[ALARM, 3]" in worker  # bounded 3-minute cycle, preserved on cold starts
    assert "[HEARTBEAT_ALARM, 1]" in worker  # independent heartbeat
    assert "chrome.alarms.get(name)" in worker  # never reset an existing cycle
    assert "HEARTBEAT_ALARM" in worker and "heartbeatOnly" in worker
    assert manifest["version"] == "2.2.2.828"
    assert "raw_answer" in worker and "session_url" in worker and "citation_urls" in worker
    assert "external_https_session_required" in worker
    assert "answer_capture_timeout" in content
    assert "captcha" in content and "auth_required" in content
    assert "chrome.storage.local" in worker
    assert "chrome.runtime.onStartup" in worker

    bridge = (SOURCE / "backend" / "r8_19_geo_validation_patch.py").read_text(encoding="utf-8")
    runtime = (SOURCE / "integrations" / "geo_browser_agent.py").read_text(encoding="utf-8")
    assert 'origin.startswith("chrome-extension://")' in bridge
    assert "def do_options(handler):" in bridge
    assert '"Access-Control-Allow-Origin"' in bridge
    assert '"Content-Type, X-Kazuizhi-Agent"' in bridge
    assert "HEARTBEAT_TTL_SECONDS = 180" in runtime

    build = (ROOT / "04_Build" / "build_v2_windows.ps1").read_text(encoding="utf-8")
    assert "KazuizhiGeoBrowserExtension" in build
    assert "browser_extension/kazuizhi_geo" in build
    ui = (SOURCE / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    assert "#788 Chrome 常驻执行器" in ui
    print("PASS: R8-28 persistent Chrome executor, truthful receipt gate, and package integration")


if __name__ == "__main__":
    main()
