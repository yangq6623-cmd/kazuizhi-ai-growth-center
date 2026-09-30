"""R8-19 GEO Phase 1 live-field safety gate.

The owner may run GEO without paid APIs. Browser validation is the default real
external path, local models remain C-level only, and API is an optional future
acceleration channel.
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
    ui = (WEB / "operational-search.js").read_text(encoding="utf-8")
    build = (WEB / "build_info.js").read_text(encoding="utf-8")

    require('/api/r8-19/geo/preflight' in backend, 'GEO live preflight endpoint missing')
    require('browser_external_ai' in backend and 'DEFAULT_TEST_METHOD = "browser"' in backend, 'browser-first backend default missing')
    require('api_required' in backend and 'False' in backend, 'API is still treated as mandatory')
    require('/api/r8-19/geo/browser/prepare' in backend and '/api/r8-19/geo/browser/receipt' in backend, 'browser validation contract endpoints missing')
    require('/api/r8-19/geo/local-precheck/run' in backend, 'local GEO precheck endpoint missing')

    require('/geo-phase1-live-gate.js' in bridge, 'main platform does not load GEO live gate')
    require("'/api/r8-19/geo/preflight'" in gate, 'live gate does not use preflight')
    require('api_required: false' in gate, 'live gate still requires API')
    require('geo-browser-one' in gate and 'geo-browser-ten' in gate, 'browser one/ten question field controls missing')
    require('本地模型固定为C级辅助' in gate, 'local model truth warning missing')
    require('API是可选加速通道' in gate, 'optional API policy missing')

    for marker in ('本地预检1题', '网页真实验证1题', '准备10题', '保存真实网页 Evidence / Receipt', 'API执行本轮 GEO 测试（可选）'):
        require(marker in ui, f'GEO no-API UI marker missing: {marker}')

    require('phase: "R8-19"' in build, 'visible build identity is not R8-19')
    require('R8-19 GEO Phase 1' in build, 'visible R8-19 GEO Phase 1 label missing')
    require('R8-18' not in build, 'stale R8-18 identity remains in build_info.js')

    print('PASS: R8-19 GEO live gate defaults to browser validation, keeps local model C-level, and treats API as optional')


if __name__ == '__main__':
    main()
