"""R8-19 GEO Phase 1 live-field safety gate.

This regression test protects the owner workflow used before the first real GEO
question is sent to an external AI. It does not fake external evidence; it only
verifies that the packaged product refuses to enqueue/run official GEO work
until the external validator is verified, then defaults to a one-question field
check before the 10-question round.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
BACKEND = ROOT / "05_V2.0.0_Source" / "backend" / "r8_19_geo_validation_patch.py"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    backend = BACKEND.read_text(encoding="utf-8")
    bridge = (WEB / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    gate = (WEB / "geo-phase1-live-gate.js").read_text(encoding="utf-8")
    build = (WEB / "build_info.js").read_text(encoding="utf-8")

    require('/api/r8-19/geo/preflight' in backend, 'GEO live preflight endpoint missing')
    require('require_executor_ready' in backend, 'GEO planning lacks executor-ready safety gate')
    require('先完成外部AI授权/连接验证' in backend, 'preflight next-step guidance missing')
    require('api_or_permission' in backend, 'unconfigured external validator is not surfaced to 待我处理')

    require('/geo-phase1-live-gate.js' in bridge, 'main platform does not load GEO live gate')
    require('geo-run-one' in gate and '先验证 1 题' in gate, 'one-question field validation control missing')
    require("'/api/r8-19/geo/preflight'" in gate, 'one-question control does not run preflight')
    require('require_executor_ready: true' in gate, 'browser planning can still enqueue before executor verification')
    require("local model" not in gate.lower() or '本地模型不能冒充正式 GEO 证据' in gate, 'local model truth warning missing')
    require('result.receipt?.official_truth' in gate, 'UI counts completion without official Receipt')

    require('phase: "R8-19"' in build, 'visible build identity is not R8-19')
    require('R8-19 GEO Phase 1' in build, 'visible R8-19 GEO Phase 1 label missing')
    require('R8-18' not in build, 'stale R8-18 identity remains in build_info.js')

    print('PASS: R8-19 GEO live gate requires verified external AI and starts with one real question')


if __name__ == '__main__':
    main()
