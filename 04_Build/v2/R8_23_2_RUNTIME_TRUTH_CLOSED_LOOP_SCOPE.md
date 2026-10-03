# R8-23.2 Pilot RC1 — Runtime Truth & Closed-Loop Acceptance

R8-23.2 is the first field-testable convergence candidate. It does not add another business center. It freezes the feature surface and closes the truth, resilience, routing and owner-UI gaps required before production certification.

## Permanent architecture

Boss → ChatGPT sole strategic controller → bounded Decision Pack → single active Command → Mission → Controller Plan → employee-owned Task → deterministic local scheduler/workers → selected model/tool/connector → Receipt/Evidence → real SEO/GEO/business feedback → ChatGPT review → next cycle.

Two growth engines remain first-class: repair services and personal tasks. Eight AI employees remain concrete work owners.

Model routing is task-based, not a rigid percentage split:
- Local model is preferred for high-frequency, low-risk, batch classification/drafting/pre-check work.
- RTX 3060 is preferred local compute when an eligible image/video/GPU job exists.
- Doubao is required for selected high-value SEO/GEO stages (keyword/search-intent enhancement, important SEO semantic QC/content, GEO question expansion, GEO gap analysis, GEO content optimization/QC) and otherwise acts as augmentation/fallback.
- ChatGPT owns strategy, priority, cross-team decisions, exception replanning and review; it is not a per-task heartbeat dependency.
- Ordinary local/Doubao/API output remains C-level auxiliary for GEO. Formal GEO requires real external A/B Evidence.

## 19 engineering work packages

1. **Single runtime version truth** — one `core/release_manifest.json` feeds current `/api/status`, `/api/version`, readiness and owner-facing runtime identity. Legacy R7/R8 identity files remain compatibility history only.
2. **Single active Command/Mission/Plan/Task truth** — canonical current chain and consistency gate; old commands are historical, not competing current truth.
3. **Receipt/Evidence state machine** — CONFIGURED, INVOKED, GENERATED, QC_PASSED, PUBLISHED, SUBMITTED, CRAWLED, INDEXED, RANKED, FORMAL_EVIDENCE and business outcomes are distinct non-promotable states.
4. **Scheduler wait-queue governance** — every queued item carries a wait reason, due time, retry information and ready/scheduled distinction.
5. **Duplicate/orphan/idempotency governance** — deterministic idempotency key suppresses exact duplicate current work; command/mission binding remains explicit.
6. **Crash/restart recovery** — stale non-financial local running work can safely re-enter the queue under a bounded recovery count; inherited runtime-resilience restart/heartbeat remains active.
7. **Local failure isolation** — model/API/channel faults degrade the affected capability instead of blocking the core Mission.
8. **7×24 event-driven/night autonomy** — Decision Pack lease allows already-authorized non-financial monitoring/execution to continue without an interactive browser chat being a heartbeat dependency.
9. **AI employee/pipeline status convergence** — current task truth is tied to one Command/Mission and surfaced in the owner truth strip rather than inferred from unrelated historical counters.
10. **Human-pending purification** — Controller Plan/scheduler waiting is system-owned; only real captcha/login/identity/core authorization/funds gates reach the owner.
11. **SEO real closed-loop semantics** — generation/QC/public verification/search submission/crawl/index/rank remain separate and require real receipts at each promotion.
12. **GEO real closed-loop semantics** — Phase 3/public content/external retest/formal A/B Evidence remain separate; C-level model scans never inflate formal results.
13. **One real social platform first** — graded L1→L4 platform/account/action authority is preserved; autonomous expansion to a second platform requires a real first-platform Post ID/URL/Receipt loop. The installer provides the enforcement/readiness path; the real external proof is a field-acceptance result, not fabricated in CI.
14. **Business attribution to order only** — site visit → mini-program visit → consultation → task → order. Money/amount/revenue/profit/ROI stay outside autonomous business metrics.
15. **Unified Health/Readiness/Version API contract** — `/api/health`, `/api/runtime-health`, `/api/version`, `/api/readiness`, and `/api/r8-23-2/runtime-truth` expose distinct liveness/readiness/truth meanings.
16. **Security/authorization/supply-chain truth** — DPAPI credential vault and graded authority remain; installer signing is supported only when a real Authenticode certificate is configured. Unsigned builds must never claim to be signed.
17. **ChatGPT Decision Pack / TTL / control lease** — 24-hour bounded plan includes objective, IDs, employees, model policy, authorization boundaries, success contract and fallback. Expiry blocks new strategic expansion while health/recovery/read-only work may continue.
18. **Final owner UI convergence** — compact current-truth strip, no repeated full cockpit on every page, owner-facing Chinese status semantics, legacy/technical views treated as audit rather than current truth.
19. **Metric time/state semantics** — current truth explicitly separates queue state and result stages; owner pages must distinguish current-cycle/today/history when rendering counters and must not equate connection readiness with external success.

## Field acceptance gates — not replaceable by CI

### Gate 20 — 24h real Windows unattended run
Must prove: no crash, no active-command conflict, no duplicate current work, no fake external completion, continuous receipts, automatic retry/recovery, and at least one real owned-site publish/search receipt when external prerequisites are available.

### Gate 21 — 72h real fault/recovery run
Must include controlled network/model/API/channel interruption and verify local degradation, continued unaffected work, bounded retry and recovery after the dependency returns.

### Gate 22 — 7-day real production run
Must prove the complete loop repeatedly over real time: signal → ChatGPT decision → Decision Pack → AI employee tasks → local/Doubao/tool execution → real URL/Post/Search/GEO/business receipts → review → next cycle.

These three gates remain `pending_real_*` in the release manifest until the corresponding physical-time field run actually passes. A 5760-cycle or other CI soak is useful engineering evidence but is not renamed as a real 24h/72h/7-day field pass.

## Production promotion rule

R8-23.2 Pilot RC1 is suitable for first landing/field testing after CI is green. It may be promoted to R8-24 Production only after Gates 20, 21 and 22 pass with real field evidence. Funds remain permanently human-only even after production certification.
