import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"

from core import version  # noqa: E402

EXPECTED_DISPLAY = "V2.1.0 Beta R8 Preview"
EXPECTED_RUNTIME = "KZ-ENTERPRISE-V2.1-BETA-20260918-R8-PREVIEW"

status = version.get_version()
if status.get("display_version") != EXPECTED_DISPLAY:
    raise AssertionError("R8 display version missing")
if status.get("runtime_build") != EXPECTED_RUNTIME:
    raise AssertionError("R8 runtime build missing")
if status.get("r8_phase") != "R8-00":
    raise AssertionError("R8 phase missing")

manifest = json.loads((SRC / "version" / "manifest.json").read_text(encoding="utf-8"))
preview = manifest.get("r8_preview") or {}
if preview.get("display_version") != EXPECTED_DISPLAY or preview.get("runtime_build") != EXPECTED_RUNTIME:
    raise AssertionError("R8 manifest identity mismatch")

web_version = (SRC / "web" / "WEB_VERSION.txt").read_text(encoding="utf-8")
identity = (SRC / "web" / "r8_identity.js").read_text(encoding="utf-8")
build_info = (SRC / "web" / "build_info.js").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
for value in (EXPECTED_DISPLAY, EXPECTED_RUNTIME, "R8-00"):
    if value not in web_version:
        raise AssertionError(f"WEB_VERSION missing {value}")
if EXPECTED_RUNTIME not in identity or EXPECTED_DISPLAY not in identity:
    raise AssertionError("R8 visible identity patch mismatch")
if "build_info.js" not in forms or "r8_identity.js" not in forms:
    raise AssertionError("R8 visible identity scripts are not loaded")
if "runNumber" not in build_info or "commit" not in build_info:
    raise AssertionError("R8 build provenance fields missing")

installer = (ROOT / "04_Build" / "installer" / "Kazuizhi_AI_V2.0.0_Beta_Setup.iss").read_text(encoding="utf-8")
windows_version = (ROOT / "04_Build" / "v2" / "windows_version.txt").read_text(encoding="utf-8")
workflow = (ROOT / ".github" / "workflows" / "build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
for value in (
    "Kazuizhi AI Enterprise V2.1.0 Beta R8 Preview",
    "Kazuizhi_AI_Enterprise_V2.1.0_R8_Preview",
):
    if value not in installer:
        raise AssertionError(f"R8 installer identity missing: {value}")
if "2.1.0.1" not in windows_version or "R8 Preview" not in windows_version:
    raise AssertionError("R8 Windows version identity missing")
if "Kazuizhi_AI_Enterprise_V2.1.0_R8_Preview" not in workflow:
    raise AssertionError("R8 artifact identity missing from workflow")

print("PASS: R8 Preview package, visible build identity, R8-00 phase and R7 compatibility layer are distinct and traceable")
