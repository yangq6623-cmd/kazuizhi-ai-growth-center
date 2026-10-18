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
    import core.r8_growth_ops as growth
    import promotion.content_center as promotion

    importlib.reload(growth)
    importlib.reload(promotion)

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
    # R8-23 uses automatic quality control: imported drafts are approved for
    # account-scoped queueing, but are never treated as externally published
    # without a real platform receipt.
    assert imported["item"]["approval_state"] == "approved"
    assert imported["item"]["approved_by"] == "automation_qc"
    duplicate = growth.import_promotion_draft({"draft_id": draft["id"], "platform": "douyin"})
    assert duplicate["created"] is False

    audit = growth.diagnostics()
    assert [row["step"] for row in audit["checks"]] == list(range(11))
    assert 0 <= audit["score"] <= 10
    assert audit["evidence"]["content_drafts"] == 1
    assert audit["evidence"]["published_urls"] == []
    assert "不能验证搜索收录" in audit["evidence"]["indexing_status"]

pyramid = (SRC / "web" / "r8_command_pyramid.js").read_text(encoding="utf-8")
identity = (SRC / "web" / "r8_identity.js").read_text(encoding="utf-8")
promotion_ui = (SRC / "web" / "promotion.js").read_text(encoding="utf-8")
backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
assert "0→10 全链路验收" in pyramid and "一、总控与决策" in pyramid
assert "提交到 R8 审核" in promotion_ui
assert "/api/r8/growth/import-draft" in backend

# Startup stability contract: the AI command homepage must not arm any retired
# phone/mirror runtime. PC browser QR login stays in the account-center route.
assert "armDeviceRuntimeLoader();" not in identity
assert "loadFinalGrowthCenter" in identity
assert "new MutationObserver(()=>enhanceR8())" not in pyramid
assert "observer.observe(target,{subtree:true,childList:true})" not in pyramid
assert "settleEnhancements" in pyramid

print("PASS: PC browser QR runtime, bounded R8 startup, content-to-publish bridge and truthful 0-to-10 audit")
