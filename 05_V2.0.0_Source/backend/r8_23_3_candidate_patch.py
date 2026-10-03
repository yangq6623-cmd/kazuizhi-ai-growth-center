"""R8-23.3 Candidate integration.

Field-fix release for Build #62 observations: stale 24h Decision Pack authorization,
active-vs-pending Command confusion, opaque readiness, duplicate/legacy UI surfaces and
old R7 first-paint. Existing truth and finance gates are preserved.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server
from core import r8_23_2_runtime_truth as pilot
from core import r8_23_3_candidate as candidate

_INSTALLED = False

_BOOT_STYLE = r"""
<style id="kz-r8233-boot-style">
html.kz-r8233-booting body>.layout{visibility:hidden!important}
#kz-r8233-boot{position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;background:#f3f6fb;color:#172033;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif}
#kz-r8233-boot .card{width:min(560px,calc(100vw - 40px));background:#fff;border:1px solid #dfe7f2;border-radius:18px;padding:30px 34px;box-shadow:0 18px 60px rgba(24,48,91,.12)}
#kz-r8233-boot .brand{display:flex;align-items:center;gap:14px;margin:0 0 20px;color:#172033}
#kz-r8233-boot .mark{display:grid;place-items:center;width:46px;height:46px;border-radius:14px;background:linear-gradient(135deg,#2f6eea,#6b77f7);color:#fff;font-weight:800}
#kz-r8233-boot h1{font-size:22px;margin:0 0 8px}#kz-r8233-boot p{margin:0;color:#718096;line-height:1.8;font-size:13px}
#kz-r8233-boot .bar{height:6px;margin:22px 0 14px;background:#edf2f8;border-radius:99px;overflow:hidden}
#kz-r8233-boot .bar:after{content:"";display:block;width:42%;height:100%;background:#3168e8;border-radius:99px;animation:kz8233boot 1.2s ease-in-out infinite alternate}
@keyframes kz8233boot{from{transform:translateX(-10%)}to{transform:translateX(145%)}}
</style>
"""

_BOOT_HTML = r"""
<div id="kz-r8233-boot" role="status" aria-live="polite"><div class="card">
  <div class="brand"><span class="mark">KZ</span><div><h1>卡嘴子 AI 自治运营</h1><p>R8-23.3 Candidate · Runtime Execution & UI Convergence</p></div></div>
  <div class="bar"></div><p data-kz-boot-status>正在恢复 Mission、控制租约、任务队列与模型连接；完成版本握手后进入正式界面。</p>
</div></div>
"""

_BOOT_SCRIPT = "<script>document.documentElement.classList.add('kz-r8233-booting')</script>"


def _patch_runtime_truth():
    """Keep old R8-23.2 API contracts but make all of them read Candidate truth."""
    pilot.PILOT_VERSION = candidate.CANDIDATE_VERSION
    pilot.release_manifest = candidate.release_manifest
    pilot.single_truth = candidate.single_truth
    pilot.decision_pack = candidate.decision_pack
    pilot.queue_diagnostics = candidate.queue_diagnostics
    pilot.readiness = candidate.readiness
    pilot.snapshot = candidate.snapshot


def _serve_candidate_index(handler):
    source = (server.get_web_path() / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        "<head>",
        "<head>" + _BOOT_SCRIPT + _BOOT_STYLE,
        1,
    )
    source = source.replace(
        "<title>卡嘴子 AI 增长运营中心 V2.0.0 Beta R7 Final</title>",
        "<title>卡嘴子 AI 自治运营 · R8-23.3 Candidate</title>",
        1,
    )
    source = source.replace("<body>", "<body>" + _BOOT_HTML, 1)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
    names = [
        "autonomous-ops.js",
        "r8_22_autonomy.js",
        "r8_23_growth_os.js",
        "r8_23_2_pilot.js",
        "r8_23_3_candidate.js",
    ]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_runtime_truth()

    original_get = server.DashboardHandler.do_GET

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path in {"/", "/index.html"}:
                _serve_candidate_index(handler)
                return
            if path == "/autonomous-ops.js":
                _serve_autonomous_ops(handler)
                return
            if path in {"/api/r8-23-3/candidate", "/api/r8-23-3/runtime-truth"}:
                handler._json_ok(candidate.snapshot())
                return
            if path == "/api/r8-23-3/execution":
                handler._json_ok(candidate.queue_diagnostics())
                return
            if path == "/api/r8-23-3/attention":
                handler._json_ok(candidate.attention_summary())
                return
            if path == "/api/r8-23-3/control-lease":
                handler._json_ok(candidate.controller_lease())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_r8_23_3_candidate = True
    _INSTALLED = True


install()
