from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
WEB = SRC / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    startup = (WEB / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    seo_geo = (WEB / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    index = (WEB / "index.html").read_text(encoding="utf-8")
    run = (SRC / "run.py").read_text(encoding="utf-8")
    server = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
    seo_patch = (SRC / "backend" / "r8_13_seo_geo_patch.py").read_text(encoding="utf-8")

    require("const SCRIPT_TIMEOUT_MS = 12000" in startup, "cold-start module timeout is too short")
    require("SCRIPT_RETRY_DELAY_MS" in startup, "startup has no one-time retry for a busy local server")
    require("await loadScript(src, key);" in startup, "startup retry no longer reloads the module")
    require("controller.abort(),15000" in seo_geo, "SEO/GEO snapshot timeout is shorter than the cold-start evidence request")
    require("ensureSeoGeoBridge" in startup, "SEO/GEO navigation has no interrupted-start recovery")
    require("r813SeoGeoRecovery" in startup, "SEO/GEO recovery script marker is missing")
    require("retryFailedModules" in startup and "auto_retry_" in startup, "cold-start owner modules are not retried after the UI becomes usable")
    require("loadPostReadyModules" in startup and "POST_READY_TIMEOUT_MS = 45000" in startup, "post-ready modules do not have a quiet long-timeout recovery path")
    require("POST_READY_DELAY_MS = 5000" in startup, "post-ready modules still compete with the cold-start owner shell")
    require("KZClearStartupModuleFailure" in startup, "route recovery cannot clear stale startup failure state")
    require("probeServiceHealth" in seo_geo and "/api/r8-13/seo-geo/health" in seo_geo, "SEO/GEO page lacks lightweight service health probe")
    require("loadBusy" in seo_geo and "loadPending" in seo_geo, "SEO/GEO polling can overlap itself")
    require("SEO/GEO实时刷新延后" in seo_geo, "SEO/GEO page cannot distinguish delayed refresh from offline service")
    require("LAST_GOOD_KEY" in seo_geo and "restoreLastGood" in seo_geo and "persistLastGood" in seo_geo, "SEO/GEO page cannot preserve a real last-good snapshot across iframe reloads")
    require("build_info.js?probe=" in seo_geo, "SEO/GEO status does not distinguish static local service health from a busy API queue")
    require('defer src="r8_12_startup_coordinator.js" data-r812-startup-coordinator="1"' in index, "the startup coordinator is not parallel-deferred")
    require("sourceCache" in startup and "sourcePromises" in startup and "primeScriptSources" in startup, "owner-shell sources are still downloaded sequentially")
    require("seo_geo: [" in startup and "r8_13_seo_geo_bridge.js" in startup, "SEO/GEO first-click bridge is not prefetched/lazy-cached")
    require("request_queue_size = 64" in server and "daemon_threads = True" in server, "local HTTP server cannot absorb the owner-shell cold-start burst")
    for token in ("SCHEDULER_STARTUP_GRACE_SECONDS = 12", "CONTENT_STARTUP_GRACE_SECONDS = 25", "RELAY_STARTUP_GRACE_SECONDS = 20", "VIDEO_STARTUP_GRACE_SECONDS = 35", "HEAVY_CONTROL_STARTUP_GRACE_SECONDS = 45"):
        require(token in run, f"background worker cold-start grace missing: {token}")
    require("next_heavy_at = time.monotonic()" in run and "HEAVY_CONTROL_INTERVAL_SECONDS" in run, "heavy control/network work still starts on tick zero")
    require("_SNAPSHOT_REFRESH_PENDING" in seo_patch and "threading.Timer" in seo_patch, "SEO/GEO full snapshot refresh still competes with the response path")
    install_block = seo_patch.split("def install():", 1)[1].split("original_get =", 1)[0]
    require("_kick_snapshot_refresh()" not in install_block, "SEO/GEO full snapshot still starts during module import")
    print("PASS: cold-start UI loading tolerates a busy but healthy local SEO/GEO server")


if __name__ == "__main__":
    main()
