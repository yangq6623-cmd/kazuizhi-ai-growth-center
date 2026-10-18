# R8-24 GEO Field Repair #770 — install acceptance ledger

## Ground truth from owner screenshots (#769)
- 156 operational Signals, 125 GEO opportunities, 2/50 formal A/B retained.
- Advanced Evidence GET stalled in the actual desktop browser despite passing synthetic/cache CI.
- `kz_site_tools.js` listed as a startup failure, while main local-control modules were responsive.
- Separate panels (including AI decision) displayed pending/unknown states; public publish connector not ready. A SUBMITTED stage is not an independently validated real-world publish receipt.

## Changes
- Optional browser WebMCP tool JS is loaded ONLY when `modelContext.registerTool` is supported. Unsupported Chrome is truthfully labelled and does not block core connection route or falsify startup failures.
- Hidden GEO tabs no longer issue GET every 10 seconds; visible active workbench polls at 20 seconds, preserving manual refresh.
- If BOTH Evidence endpoints time out but an independent valid owner GEO snapshot exists, show that actual historical formal A/B count, clearly tagged as historical/unverified; 4/4 Evidence requires the real complete endpoint.
- Loopback HTTP diagnostics `/api/r8-24/geo-growth/http-health` report recent slow request categories and active slow GETs. Bounded in-memory only, read-only, no credentials, raw URLs, query strings or business records.
- Five concurrent stalled GEO GET stress test must keep local HTTP liveness and a tiny JS resource responsive.

## Pre-installer checks
The source-only Windows preflight workflow on `review/geo-770-load-realism-20261009` succeeded (run 37912855529). It includes JS syntax, R7/R8 owner parity, real Chrome double Evidence fault and recovery, and five parallel blocked-GET health/static tests.

## Release constraints
Windows installer, source parity, installed real Chrome GEO/advanced Evidence fault recovery, overwrite/portable separation and uninstall must all pass before delivery.
Never misreport C-level Doubao generation, SUBMITTED stage, local Mission progress, or embedded 50-question baseline as confirmed external AI A/B validation or externally verified publication.
A GitHub-hosted Windows test pass does NOT prove 24h stability on the owner's machine; ask for field screenshots and/or read-only diagnostics if local faults persist.
