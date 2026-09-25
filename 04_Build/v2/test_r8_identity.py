import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from core import version  # noqa: E402

EXPECTED_DISPLAY = "V2.2.2 自治运营核心"
EXPECTED_RUNTIME = "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
EXPECTED_CORE_PHASE = "R8-09"
EXPECTED_WEB_PHASE = "R8-17"
EXPECTED_PRODUCT = "Kazuizhi AI Enterprise V2.2.2 R8 Autonomous Mission Core"
EXPECTED_INSTALLER = "Kazuizhi_AI_Enterprise_V2.2.2_R8_Autonomous_Mission_Core"

status = version.get_version()
if status.get("display_version") != EXPECTED_DISPLAY:
    raise AssertionError("R8 display version missing")
if status.get("runtime_build") != EXPECTED_RUNTIME:
    raise AssertionError("R8 runtime build missing")
if status.get("r8_phase") != EXPECTED_CORE_PHASE:
    raise AssertionError("R8 core phase missing")
if status.get("product") != EXPECTED_PRODUCT:
    raise AssertionError("R8 product identity missing")

manifest = json.loads((SRC / "version" / "manifest.json").read_text(encoding="utf-8"))
preview = manifest.get("r8_final") or {}
if preview.get("display_version") != EXPECTED_DISPLAY or preview.get("runtime_build") != EXPECTED_RUNTIME:
    raise AssertionError("R8 manifest identity mismatch")
if preview.get("phase") != EXPECTED_CORE_PHASE:
    raise AssertionError("R8 manifest core phase mismatch")

web_version = (SRC / "web" / "WEB_VERSION.txt").read_text(encoding="utf-8")
identity = (SRC / "web" / "r8_identity.js").read_text(encoding="utf-8")
build_info = (SRC / "web" / "build_info.js").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
final_center = (SRC / "web" / "r8_final_center.js").read_text(encoding="utf-8")
final_style = (SRC / "web" / "r8_final.css").read_text(encoding="utf-8")
social_center = (SRC / "web" / "social_media_center.js").read_text(encoding="utf-8")
for value in ("V2.2.2 Autonomous Mission Core", EXPECTED_RUNTIME, EXPECTED_WEB_PHASE):
    if value not in web_version:
        raise AssertionError(f"WEB_VERSION missing {value}")
if EXPECTED_RUNTIME not in identity or EXPECTED_DISPLAY not in identity or EXPECTED_CORE_PHASE not in identity:
    raise AssertionError("R8 core visible identity patch mismatch")
if EXPECTED_WEB_PHASE not in build_info:
    raise AssertionError("R8 current web phase missing from build provenance")
if "build_info.js" not in forms or "r8_identity.js" not in forms:
    raise AssertionError("R8 visible identity scripts are not loaded")
if "runNumber" not in build_info or "commit" not in build_info:
    raise AssertionError("R8 build provenance fields missing")
for marker in ("r8_final.css", "r8_final_center.js", "loadFinalGrowthCenter"):
    if marker not in identity:
        raise AssertionError(f"R8 Final center loader missing {marker}")
for label in ("升级总控", "情报雷达", "内容委员会", "3060视频工厂", "审核与发布", "消息与线索", "归因与学习", "审计与体检"):
    if label not in final_center:
        raise AssertionError(f"R8 Final UI missing tab: {label}")
for route in ("/api/r8/growth/signals", "/api/r8/growth/publishing/receipt", "/api/r8/growth/learning/run", "/api/r8/growth/diagnostics"):
    if route not in final_center:
        raise AssertionError(f"R8 Final UI route missing: {route}")
if ".r8-final-tabs" not in final_style or ".r8-gate-grid" not in final_style:
    raise AssertionError("R8 Final responsive style contract missing")
for field in ("social-form-role", "social-form-level", "social-form-region", "social-form-service"):
    if field not in social_center:
        raise AssertionError(f"R8 account-matrix UI field missing: {field}")

installer = (ROOT / "04_Build" / "installer" / "Kazuizhi_AI_V2.0.0_Beta_Setup.iss").read_text(encoding="utf-8")
windows_version = (ROOT / "04_Build" / "v2" / "windows_version.txt").read_text(encoding="utf-8")
workflow = (ROOT / ".github" / "workflows" / "build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
for value in (EXPECTED_PRODUCT, EXPECTED_INSTALLER):
    if value not in installer:
        raise AssertionError(f"R8 installer identity missing: {value}")
if "2.2.2.22" not in windows_version or EXPECTED_PRODUCT not in windows_version:
    raise AssertionError("R8 Windows version identity missing")
if EXPECTED_INSTALLER not in workflow:
    raise AssertionError("R8 artifact identity missing from workflow")

print("PASS: V2.2.2 Autonomous Mission Core package, R8-09 core identity, R8-17 web phase and R7 compatibility are traceable")
