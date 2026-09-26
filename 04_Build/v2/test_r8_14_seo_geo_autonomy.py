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
    assert result["skipped"] is True
    assert result["reason"] == "chatgpt_not_verified"

    assisted = configure({"mode": "assisted"})
    assert assisted["mode"] == "assisted"
    result = run_once(force=True)
    assert result["reason"] == "chatgpt_not_verified"
    snap = dashboard()
    assert len(snap.get("assets", [])) == 0
    # No local UI mode is allowed to bypass the verified ChatGPT command gate.
    assert all(a.get("stage") not in {"PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"} for a in snap.get("assets", []))

    autonomous = configure({"mode": "autonomous"})
    assert autonomous["mode"] == "autonomous"
    result = run_once(force=True)
    assert result["reason"] == "chatgpt_not_verified"
    state = status()
    keys = {x.get("key") for x in state["human_items"]}
    assert "chatgpt_seo_geo_daily_plan" in keys
    assert state["chatgpt_control"]["gate"]["allowed"] is False
    assert state["policy"]["never_fake_publication"] is True
    assert state["policy"]["never_fake_indexing"] is True
    assert state["policy"]["never_fake_geo_visibility"] is True
    assert all("授权至少一个搜索站长平台" != x.get("title") for x in state["human_items"])

    ui = (SOURCE / "web" / "r8_14_seo_geo_autonomy_ui.js").read_text(encoding="utf-8")
    for marker in ("ChatGPT 总控", "等待 ChatGPT 总控计划", "SEO/GEO 待处理", "/api/r8-14/seo-geo/autonomy"):
        assert marker in ui, marker
    for marker in ("r814-feedback", "kz-r813-focus", "刷新失败：", "已完成总控计划核对"):
        assert marker in ui, marker

    print("PASS: R8-14 SEO/GEO execution is blocked until the verified ChatGPT daily plan gate opens.")


if __name__ == "__main__":
    main()
