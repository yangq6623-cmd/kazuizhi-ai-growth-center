import importlib
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))


with tempfile.TemporaryDirectory() as temp_dir:
    os.environ["LOCALAPPDATA"] = temp_dir
    import core.r8_control as control
    import core.r8_growth_ops as growth
    import promotion.content_center as promotion

    importlib.reload(control)
    importlib.reload(growth)
    importlib.reload(promotion)

    control.register_device({"device_id": "PHONE-001", "label": "验收手机"})
    control.record_device_probe("PHONE-001", True, source="adb", detail="test")
    draft = promotion.generate_ad({
        "region": "涟水",
        "service": "家电维修",
        "keyword": "涟水家电维修",
        "audience": "本地真实需求用户",
        "evidence": "仅使用已核实的平台服务范围",
    })
    imported = growth.import_promotion_draft({"draft_id": draft["id"], "platform": "douyin"})
    assert imported["created"] is True
    assert imported["item"]["source_draft_id"] == draft["id"]
    assert imported["item"]["approval_state"] == "pending"
    duplicate = growth.import_promotion_draft({"draft_id": draft["id"], "platform": "douyin"})
    assert duplicate["created"] is False

    audit = growth.diagnostics()
    assert [row["step"] for row in audit["checks"]] == list(range(11))
    assert 0 <= audit["score"] <= 10
    assert audit["evidence"]["content_drafts"] == 1
    assert audit["evidence"]["published_urls"] == []
    assert "不能验证搜索收录" in audit["evidence"]["indexing_status"]


import integrations.android_device as device

device._SCREENSHOT_CACHE.clear()
calls = []
original_run = device._run
try:
    def fake_run(arguments, timeout=8, binary=False):
        calls.append(tuple(arguments))
        if arguments[-1] == "get-state":
            return "device\n"
        return b"\x89PNG\r\n\x1a\n" + b"frame"

    device._run = fake_run
    first = device.screenshot_bytes("PHONE-001")
    second = device.screenshot_bytes("PHONE-001")
    assert first == second
    assert sum(1 for row in calls if "screencap" in row) == 1
finally:
    device._run = original_run
    device._SCREENSHOT_CACHE.clear()


mirror = (SRC / "web" / "r8_device_b4_mirror_hotfix.js").read_text(encoding="utf-8")
pyramid = (SRC / "web" / "r8_command_pyramid.js").read_text(encoding="utf-8")
promotion_ui = (SRC / "web" / "promotion.js").read_text(encoding="utf-8")
backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
assert mirror.index("function hasFrame") < mirror.index("function showEmpty")
assert "if (!hasFrame()) showEmpty" in mirror
assert "clearTimeout" in mirror and "continuousEnabled" in mirror
assert "0→10 全链路验收" in pyramid and "一、总控与决策" in pyramid
assert "提交到 R8 审核" in promotion_ui
assert "/api/r8/growth/import-draft" in backend

print("PASS: stable phone frames, content-to-publish bridge, Chinese command pyramid and 0-to-10 truthful audit")
