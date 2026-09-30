from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


html = read("content-studio.html")
shell = read("content-studio-shell.js")
easy = read("content-studio-easy-front.js")
polish = read("content-studio-b2b-polish.css")

routes = re.findall(r'class="studio-tab(?: active)?" data-route="([^"]+)"', html)
expected_routes = [
    "overview",
    "intelligence",
    "reference",
    "creative",
    "director",
    "content",
    "assets",
    "qc",
    "library",
]
require(routes == expected_routes, f"content center route order changed: {routes}")

require("content-studio-b2b-polish.css" in shell, "B2B polish stylesheet is not injected into content studio iframe")
require("data-kz-b2b-polish" in shell, "B2B polish injection must be idempotent")
require("--kz-ui-gap:16px" in polish, "major content-center spacing must use the 16px grid")
require("--kz-ui-control:36px" in polish, "content-center controls must keep the 36px baseline")
require(".studio-status.amber" in polish and ".studio-status.red" in polish, "semantic status colors are incomplete")
require("font-variant-numeric:tabular-nums" in polish, "numeric/time alignment guard is missing")

require("createTreeWalker" in easy, "result copy should be changed through text nodes without rebuilding the DOM")
require("result.innerHTML = after" not in easy, "result rendering must not replace innerHTML and drop button listeners")
require("markQueueMismatch" in easy, "partial candidate queue failures need a visible truth-state guard")
require("queued >= total" in easy, "queue mismatch guard must distinguish complete and partial queueing")
require("kz-easy-queue-warning" in easy, "partial queue warning UI is missing")

print("PASS: R8-19 content center UI/interaction QA gate")
