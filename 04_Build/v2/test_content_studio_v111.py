"""Static regression gate for the V111 B-end content-center visual/status closure.

The patch must remain additive: all original routes and business copy stay in
content-studio.html, while V111 only adds styling and truthful status hydration.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"

html = (WEB / "content-studio.html").read_text(encoding="utf-8")
js = (WEB / "content-studio-v111.js").read_text(encoding="utf-8")
build = (WEB / "build_info.js").read_text(encoding="utf-8")

# The nine existing routes and their user-facing names must not be removed.
for route, label in (
    ("overview", "创导总览"),
    ("intelligence", "内容情报"),
    ("reference", "参考内容"),
    ("creative", "创意策划"),
    ("director", "AI 导演"),
    ("content", "生产工作台"),
    ("assets", "资产中心"),
    ("qc", "AI 质检"),
    ("library", "成片库"),
):
    assert f'data-route="{route}"' in html
    assert label in html

# V111 is loaded after the established #92/#101 modules.
assert "content-studio-v111.js" in build
assert "CONTENT-V101" in build
assert "UI-V111" in build

# Design contract: compact 16px grid, 36px controls, semantic status colors,
# tabular numeric/time alignment and dark navigation are represented explicitly.
for token in (
    "gap:16px",
    "height:36px",
    "font-variant-numeric:tabular-nums",
    "--v111-green",
    "--v111-amber",
    "--v111-red",
    ".studio-nav",
    ".studio-primary",
    ".studio-secondary",
):
    assert token in js, token

# Truthful hydration: the three screenshots that exposed stale static states
# (assets=0, QC empty, final library empty) must now read real local APIs.
assert "/api/ai-content-center" in js
assert "/api/series-asset-center" in js
for function_name in ("refreshAssets", "refreshQc", "refreshLibrary"):
    assert f"function {function_name}" in js

# Candidate videos must never be relabelled as finals in the library.
assert "/最终成片|完整成片/" in js
assert "!/候选/.test(kind)" in js

# QC must preserve manual review whenever semantic evidence is unavailable.
assert "待人工" in js
assert "技术/结构通过" in js
assert "director_qc" in js and "technical_qc" in js

print("V111 content-center visual/status regression gate passed")
