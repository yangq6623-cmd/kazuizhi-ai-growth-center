"""Fail closed if the 360 host fix is packaged or advertised as the old extension.

This is a source/package contract test; it never contacts an external AI site.
"""
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]
EXTENSION = ROOT / "05_V2.0.0_Source/browser_extension/kazuizhi_geo"
VERSION = "2.2.2.891"


def main():
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == VERSION
    assert "https://work.n.cn/*" in manifest["host_permissions"]
    assert "https://work.n.cn/*" in manifest["content_scripts"][0]["matches"]
    assert manifest["background"]["service_worker"] == "service-worker.js"

    worker = (EXTENSION / "service-worker.js").read_text(encoding="utf-8")
    assert 'so360_ai_search: {url: "https://work.n.cn/"' in worker
    assert "chrome.runtime.getManifest().version" in worker

    runtime = (ROOT / "05_V2.0.0_Source/integrations/geo_browser_agent.py").read_text(encoding="utf-8")
    assert runtime.count(f'"{VERSION}"') >= 4
    assert '"2.2.2.854"' in runtime  # existing extension remains compatible during controlled upgrade

    workflow = (ROOT / ".github/workflows/build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
    bundle = f"Kazuizhi_GEO_Chrome_Extension_{VERSION}.zip"
    assert workflow.count(bundle) >= 3
    assert f"Package GEO Chrome extension {VERSION}" in workflow
    assert "python 04_Build/v2/test_890_geo_extension_identity.py" in workflow
    assert "Kazuizhi_GEO_Chrome_Extension_2.2.2.854.zip" not in workflow

    installer = (ROOT / "04_Build/build_v2_windows.ps1").read_text(encoding="utf-8")
    assert "KazuizhiGeoBrowserExtension" in installer
    assert "browser_extension/kazuizhi_geo" in installer
    print("PASS: 360 work.n.cn permission, 891 identity, runtime contract and standalone/installer packaging")


if __name__ == "__main__":
    main()
