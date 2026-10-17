"""R8-19 GEO live-field safety gate.

Browser validation is the default real external path, local models remain
C-level only, and paid API is optional. The old API-oriented click-capture gate
must not be injected because it can intercept the browser-first controls.

This is a cross-phase regression gate: later R8-20/R8-21/R8-22/R8-23 releases
must preserve all R8-19 live validation contracts while allowing the visible
build label to advance beyond R8-19.
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
    polish = (WEB / "geo-phase1-ui-polish.js").read_text(encoding="utf-8")
    ui = (WEB / "operational-search.js").read_text(encoding="utf-8")
    build = (WEB / "build_info.js").read_text(encoding="utf-8")

    require('/api/r8-19/geo/preflight' in backend, 'GEO live preflight endpoint missing')
    require('browser_external_ai' in backend and 'DEFAULT_TEST_METHOD = "browser"' in backend, 'browser-first backend default missing')
    require('api_required' in backend and 'False' in backend, 'API is still treated as mandatory')
    require('/api/r8-19/geo/browser/prepare' in backend and '/api/r8-19/geo/browser/receipt' in backend, 'browser validation contract endpoints missing')
    require('/api/r8-19/geo/local-precheck/run' in backend, 'local GEO precheck endpoint missing')

    require('geo-phase1-live-gate.js' not in bridge, 'legacy API click gate is still injected into the browser-first workspace')
    require('injectGeoLiveGate' not in bridge, 'legacy GEO click-gate injector remains active')
    require('installInteractionRepair' in polish, 'browser-first button interaction repair is missing')
    require("event.stopImmediatePropagation()" in polish, 'new GEO controller does not protect controls from duplicate legacy handlers')
    require("'/api/r8-19/geo/browser/prepare'" in polish, 'browser-first UI does not call browser prepare endpoint')
    require("'/api/r8-19/geo/browser/receipt'" in polish, 'browser-first UI does not call browser receipt endpoint')
    require('API 当前不是必需项' in polish, 'optional API policy is not visible in primary command area')

    for marker in ('本地预检1题', '网页真实验证1题', '准备10题', '保存真实网页 Evidence / Receipt', 'API执行本轮 GEO 测试（可选）'):
        require(marker in ui, f'GEO no-API base UI marker missing: {marker}')

    supported_visible_phases = (
        'R8-19', 'R8-20', 'R8-21', 'R8-22', 'R8-23',
        'R8-23.3 Candidate', 'R8-23.4 Candidate',
    )
    require(any(f'phase: "{phase}"' in build for phase in supported_visible_phases), 'visible build identity is older than R8-19 or untraceable')
    require(any(phase in build for phase in supported_visible_phases), 'visible R8-19+ release label missing')
    require('R8-18' not in build, 'stale R8-18 identity remains in build_info.js')

    print('PASS: R8-19 browser-first GEO regression remains intact under the current R8-19+ visible release label')


if __name__ == '__main__':
    main()
