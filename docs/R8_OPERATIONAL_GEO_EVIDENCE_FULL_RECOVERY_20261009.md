# R8-24 GEO / Evidence / Startup Recovery — 2026-10-09

## Field evidence (#766)
- Owner GEO dashboard loads and shows genuine C-level operational counts (156 signals, 120 opportunities), and formal GEO A/B 2/50.
- Advanced Evidence 50-question baseline displays but main compact Evidence request times out after 8 seconds. A healthy evidence-health alone did NOT prove the advanced pane was rendered.
- Connection diagnostics showed three locally served UI modules failed: kz_site_tools.js, kz_local_direct_ui.js, kz_async_control_ui.js.

## Deterministic root cause and fixes
1. `r8_12_startup_coordinator.js` retryFailedModules only searched SCRIPT_SEQUENCE + POST_READY_SEQUENCE, never LAZY_SEQUENCE.connections. These exact three modules therefore could not be retried. Recovery now registers all lazy sequences without silently clearing unknown failures.
2. GEO advanced UI used a single evidence-compact GET, and on a browser-side stall left only the offline 50-question baseline and unknown official results. It now checks the tiny read-only evidence-health cache as a bounded fallback. If the cache is ready, it shows the last real formally verified A/B count and explicit "details unverified" warning, then continues retrying the full 4/4 detail request. No fake A/B or 0 counts.
3. evidence-health now returns only minimal last-known formal Evidence summary directly from a lock-free already-built cache. No new disk or external model reads are introduced.
4. The installed real-Chrome acceptance gate injects evidence-compact failure and verifies truthful fallback -> full 4/4 recovery; source-level Windows Chrome E2E passed before this packaging branch was created.

## Independent source preflight
Workflow GEO Evidence Internal Preflight (No Installer): source HTTP, regression, JavaScript, startup parity and real Chrome fault recovery passed on review/geo-evidence-e2e-20261009 at commit 0da01958bb9fcdf8d8b5722f26ff03017e392114.

## Packaging acceptance
- Windows install/launch/overwrite/uninstall must pass.
- Direct GEO workbench, Evidence 50 baseline, verified A/B summary, fault fallback and full 4/4 recovery must pass in Chrome.
- Existing SEO screens and data preserved.
- Do not treat C-level Doubao content generation as an independent formal A/B result.
- Do not claim 24-hour unattended operation or actual external AI verification from unit or packaging tests alone.
