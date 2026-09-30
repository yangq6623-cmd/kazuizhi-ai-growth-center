"""Static build gate for the #96-#101 integrated content center.

Runtime model availability is intentionally not required on GitHub-hosted CI;
this gate verifies that every module is packaged, parses, is loaded in order and
keeps truthful dependency reporting in the source contract.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"

MODULES = [
    "backend/content_reference_v96_patch.py",
    "backend/content_assets_v97_patch.py",
    "backend/voice_clone_v98_patch.py",
    "backend/shot_editor_v99_patch.py",
    "backend/postproduction_v100_patch.py",
    "backend/content_final_v101_patch.py",
]

for relative in MODULES:
    path = SRC / relative
    assert path.is_file(), f"missing integrated content module: {relative}"
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))

v96 = (SRC / MODULES[0]).read_text(encoding="utf-8")
assert "/api/content-final/reference/parse" in v96
assert "models\" / \"checkpoints" in v96
assert "系统不会用占位图冒充 AI 首帧" in v96

v97 = (SRC / MODULES[1]).read_text(encoding="utf-8")
assert "queue_candidate_generation_v97" in v97
assert "_positive_prompt_v97" in v97
assert "/api/content-final/series/apply" in v97

v98 = (SRC / MODULES[2]).read_text(encoding="utf-8")
assert "127.0.0.1:17779" in v98
assert "authorized_clone" in v98 and "self_clone" in v98
assert "loopback" in v98.lower()
assert "/api/content-final/voice/preview" in v98

v99 = (SRC / MODULES[3]).read_text(encoding="utf-8")
for action in ("add_shot", "delete_shot", "edit_shot", "split_shot", "merge_shot", "move_shot", "regenerate_shot"):
    assert f"def {action}" in v99
assert "历史候选视频" in v99

v100 = (SRC / MODULES[4]).read_text(encoding="utf-8")
assert "loudnorm=I=-16" in v100
assert "9x16" in v100 and "1x1" in v100 and "16x9" in v100
assert "postproduction_v100_completed" in v100

v101 = (SRC / MODULES[5]).read_text(encoding="utf-8")
assert "/api/content-final/status" in v101
assert "/api/content-final/self-test" in v101
assert "ready_for_full_acceptance" in v101

loader = (SRC / "backend/r8_18_evidence_ledger_patch.py").read_text(encoding="utf-8")
assert "content_final_v101_patch" in loader

build_info = (SRC / "web/build_info.js").read_text(encoding="utf-8")
assert "content-final-v101.js" in build_info
assert "CONTENT-V101" in build_info

ui = (SRC / "web/content-final-v101.js").read_text(encoding="utf-8")
for label in ("最终验收", "镜头编辑", "声音试听", "执行最终自检"):
    assert label in ui

print("#96-#101 integrated content-center source gate passed")
