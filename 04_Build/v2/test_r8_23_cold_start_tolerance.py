from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    startup = (WEB / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    seo_geo = (WEB / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")

    require("const SCRIPT_TIMEOUT_MS = 12000" in startup, "cold-start module timeout is too short")
    require("SCRIPT_RETRY_DELAY_MS" in startup, "startup has no one-time retry for a busy local server")
    require("await loadScript(src, key);" in startup, "startup retry no longer reloads the module")
    require("controller.abort(),15000" in seo_geo, "SEO/GEO snapshot timeout is shorter than the cold-start evidence request")
    require("ensureSeoGeoBridge" in startup, "SEO/GEO navigation has no interrupted-start recovery")
    require("r813SeoGeoRecovery" in startup, "SEO/GEO recovery script marker is missing")
    require("retryFailedModules" in startup and "auto_retry_" in startup, "cold-start owner modules are not retried after the UI becomes usable")
    require("loadPostReadyModules" in startup and "30000" in startup, "post-ready truth module does not have a quiet long-timeout recovery path")
    require('src="r8_12_startup_coordinator.js" data-r812-startup-coordinator="1"' in index, "the startup coordinator still depends on a later dynamic loader")
    print("PASS: cold-start UI loading tolerates a busy but healthy local SEO/GEO server")


if __name__ == "__main__":
    main()
