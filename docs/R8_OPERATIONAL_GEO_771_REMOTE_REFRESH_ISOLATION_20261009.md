# GEO #771 — isolate remote business HTTP refresh from local owner GET

## Owner's #770 field evidence
- `/api/r8-24/geo-growth/fast-health` showed status_ready=true, snapshot_age=19.62s, snapshot_stale=false, worker_count=0, last_error empty; 130 opportunities and 2/50 independently verified formal A/B, 50/50 Doubao C-level scan.
- `/api/r8-24/geo-growth/http-health` showed inflight=6, peak=7 and 517 completed requests, with repeated `other` GET requests taking approximately 20–44 seconds.
- Main owner GEO/Evidence endpoints timed out on the same PC although the independently cached snapshot was healthy. A tiny connection UI script could also time out.

## Root-cause code found
In `backend/server.py`, **every** ordinary /api/ GET except /api/r8/ triggered `refresh_business_if_due()` *before* serving the requested data. When the 300-second business connector period was due, that function synchronously called the production read-only business endpoint with a 20-second network timeout. Concurrent owner GETs could all reach the same overdue condition, launch overlapping network calls, and compete for process-wide JSON I/O locks while reporting their route as `other`.

The captured timings are highly consistent with this defect. They do not prove that *all* long requests are attributable to the connector.

## Repair
1. Owner GET routes now resolve only the requested local API, never trigger remote business sync.
2. A dedicated background timer/daemon, started and stopped with the real desktop worker group, calls the **same existing** `refresh_if_due` every 60 seconds. The original 300-second freshness condition, credentials, validation and data paths remain unchanged.
3. A single execution lock serializes automatic refresh and explicit owner POST refresh. No repeated network requests from concurrent owner GETs; no fake successful business data.
4. HTTP health reports allowlisted known endpoint families (including Mission, engine, GEO, Evidence and business status) instead of lumping all slow calls into `other`. Dynamic paths, query strings, credentials and identifying fields are never included.
5. Existing GEO cache/Evidence safeguards remain unchanged.

## Validations
Source-only GitHub Actions run 37917377999 succeeded on Windows. Specifically:
- 12 simultaneous local GETs (owner APIs + JS) responded while the simulated remote business sync was blocked.
- Background and manual sync cannot overlap.
- HTTP categories scrub dynamic routes.
- Existing GEO fast status, lock-free Evidence, SEO and Mission regressions passed.

The Windows release workflow also runs the new nonblocking test before it will build an installer. A green Windows install/browser CI does **not** prove that all other API routes are fast on the owner's machine, nor independent external GEO A/B completion. Field verification is still required.
