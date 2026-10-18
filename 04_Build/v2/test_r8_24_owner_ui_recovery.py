"""Regression gate for the owner-dashboard recovery fixes shipped after #793."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def run() -> None:
    async_ui = read("kz_async_control_ui.js")
    assert "return payload?.data ?? payload" in async_ui
    assert "window.addEventListener('focus', refresh)" in async_ui
    assert "window.addEventListener('kz:app-ready', refresh)" in async_ui

    geo = read("geo-growth-os.js")
    assert "phase1-acceptance',{timeoutMs:15000}" in geo
    assert "evidence-compact',{timeoutMs:20000}" in geo
    assert geo.count("evidence-health',{timeoutMs:8000}") >= 2

    seo = read("r8_13_seo_geo.html")
    assert "loadTimer=setTimeout(load,3000)" in seo
    assert "event.data?.type==='kz-r813-refresh'" in seo
    assert "window.addEventListener('focus',load)" in seo

    bridge = read("r8_13_seo_geo_bridge.js")
    assert "postMessage({type:'kz-r813-refresh'},location.origin)" in bridge

    cockpit = read("r8_23_growth_os.js")
    assert "new MutationObserver" not in cockpit
    assert "window.addEventListener('kz:app-ready',maintain)" in cockpit
    assert "document.addEventListener('click',maintain,true)" in cockpit

    print("R8-24 owner UI recovery regression gate passed")


if __name__ == "__main__":
    run()
