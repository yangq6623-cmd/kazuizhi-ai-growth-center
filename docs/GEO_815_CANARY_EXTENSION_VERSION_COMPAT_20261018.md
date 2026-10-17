# #815 GEO Chrome 2.2.2.814 one-shot canary compatibility

Observed on running #814 (Oct 18): connected=true, heartbeat_age_seconds=11, ready_platforms=5, extension_version=2.2.2.814, last_canary_reason=extension_version_not_808, last_retest_reason=global_retest_cooldown, last_claim_reason=queue_empty, last_error empty.

Root cause: integrations/geo_browser_agent.py exact equality `extension_version != "2.2.2.808"` guarded only the legacy one-time Doubao canary. It was not a universal browser task-claim block. Previously exhausted fixed 50-question slots and 24h retest cooldown remain independent, valid constraints.

Patch: allow only versions 2.2.2.808 and 2.2.2.814 for canary eligibility; unverified versions fail closed; do not bypass one-shot marker, attempted-question exclusion, cooldown or receipt rules. No Chrome or task data changes.

Test: isolated `python 04_Build/v2/test_geo_815_canary_version.py` asserts 808/814 enter canary eligibility while 805 is rejected, and no new question or Receipt is created; run old R7/R8 Windows regression. If failure, no installer delivery. Real browser flow/long-running 24h auto promotion remains pending site verification. Do not mistake green CI for real GEO impact.
