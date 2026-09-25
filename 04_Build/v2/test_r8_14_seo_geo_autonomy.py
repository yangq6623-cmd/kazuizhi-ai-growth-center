from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r814-seo-")

from core.seo_geo_autonomy import configure, run_once, status  # noqa: E402
from core.seo_geo_growth import dashboard  # noqa: E402


def main():
    observe = configure({"mode": "observe", "enabled": True})
    assert observe["mode"] == "observe"
    result = run_once(force=True)
    assert result["local_cycle"]["reason"] == "observe_mode"

    assisted = configure({"mode": "assisted"})
    assert assisted["mode"] == "assisted"
    result = run_once(force=True)
    assert result["mode"] == "assisted"
    snap = dashboard()
    assert len(snap.get("assets", [])) > 0
    # Deterministic local QC may advance GENERATED pages but must not fabricate public success.
    assert all(a.get("stage") not in {"PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"} for a in snap.get("assets", []))

    autonomous = configure({"mode": "autonomous"})
    assert autonomous["mode"] == "autonomous"
    result = run_once(force=True)
    assert result["external_readiness"]["publish_connector_ready"] is False
    state = status()
    keys = {x.get("key") for x in state["human_items"]}
    assert "seo_public_deploy_connector" in keys
    assert "seo_search_connector" in keys
    assert state["human_item_count"] >= 2
    assert state["policy"]["never_fake_publication"] is True
    assert state["policy"]["never_fake_indexing"] is True
    assert state["policy"]["never_fake_geo_visibility"] is True

    ui = (SOURCE / "web" / "r8_14_seo_geo_autonomy_ui.js").read_text(encoding="utf-8")
    for marker in ("观察模式", "半自动", "自治模式", "待人工处理", "/api/r8-14/seo-geo/autonomy"):
        assert marker in ui, marker
    for marker in ("r814-feedback", "kz-r813-focus", "刷新失败：", "自治状态已刷新"):
        assert marker in ui, marker

    print("PASS: R8-14 SEO/GEO autonomy modes, local-first execution and external truth gates verified.")


if __name__ == "__main__":
    main()
