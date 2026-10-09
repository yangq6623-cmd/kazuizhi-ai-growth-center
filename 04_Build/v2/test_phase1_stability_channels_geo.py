"""Release gate for Phase-1 continuity, channel truth and GEO evidence."""
from __future__ import annotations

import atexit
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
TEST_ROOT = Path(tempfile.mkdtemp(prefix=".kz-phase1-", dir=ROOT))
atexit.register(shutil.rmtree, TEST_ROOT, True)
os.environ["LOCALAPPDATA"] = str(TEST_ROOT)

from core import phase1_acceptance, runtime_supervisor  # noqa: E402
from core import geo_validation  # noqa: E402
from core.storage import write_json  # noqa: E402
from integrations import oauth_token_broker  # noqa: E402
from backend import r8_19_geo_validation_patch as geo_api  # noqa: E402


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps({"access_token": "fresh-access", "expires_in": 3600}).encode("utf-8")


def main():
    started = phase1_acceptance.start(reset=True)
    assert started["status"] == "in_progress" and started["thresholds"]["target_days"] == 7, started
    sample = phase1_acceptance.observe(
        runtime={"process": {"running": True, "pid": 100}, "health": "healthy", "workers": {"seo": {"cycles": 10, "failures": 0}}},
        search={"connectors": {"google": {"configured": True, "ready": True, "last_success_at": "2026-10-09T00:00:00+08:00"}}, "last_result": {"failed": []}},
        geo={"question_set": {"total": 50}, "official": {"tested": 2, "mentioned": 1, "recommended": 0, "cited": 1}, "evidence_completeness": {"complete": 2, "incomplete": 0}},
        supervisor={"mode": "user_scheduled_task", "installed": True, "running": True},
    )
    assert sample["geo_snapshot"]["formal_ab_completed"] == 2
    assert sample["checks"]["geo_formal_50_complete"] is False

    completed = dict(sample)
    completed["started_at"] = (datetime.now().astimezone() - timedelta(days=8)).isoformat()
    completed["target_end_at"] = (datetime.now().astimezone() - timedelta(days=1)).isoformat()
    completed["geo_snapshot"] = {**completed["geo_snapshot"], "formal_ab_completed": 50, "formal_ab_target": 50, "incomplete_evidence": 0}
    completed["max_gap_seconds"] = 60
    completed["observed_downtime_seconds"] = 0
    write_json(phase1_acceptance.STORE, completed)
    passed = phase1_acceptance.status()
    assert passed["status"] == "passed" and all(passed["checks"].values()), passed

    write_json(runtime_supervisor.INSTALL_STORE, {
        "schema": "kz.phase1-supervisor-install.v1", "installed": True,
        "mode": "user_scheduled_task", "installed_at": "2026-10-09T00:00:00+08:00",
        "detail": "test",
    })
    supervisor = runtime_supervisor.status()
    assert supervisor["installed"] is True and supervisor["install_mode"] == "user_scheduled_task", supervisor
    assert "LocalSystem" in supervisor["truth_rule"], supervisor

    account = {
        "account_id": "ACC-GSC-TEST", "platform": "google_search_console",
        "display_name": "GSC", "auth": {"platform_slot_id": "slot", "scopes": ["webmasters"]},
    }
    saved = {}
    original_get = oauth_token_broker.get_secret
    original_put = oauth_token_broker.put_secret
    original_creds = oauth_token_broker.provider_credentials
    original_open = oauth_token_broker.urlopen
    original_upsert = oauth_token_broker.upsert_official_account
    oauth_token_broker.get_secret = lambda key: "refresh-secret" if key.endswith("refresh_token") else None
    oauth_token_broker.put_secret = lambda key, value: saved.__setitem__(key, value)
    oauth_token_broker.provider_credentials = lambda platform: ("client.apps.googleusercontent.com", "client-secret")
    oauth_token_broker.urlopen = lambda request, timeout=20: _Response()
    oauth_token_broker.upsert_official_account = lambda **kwargs: {"authorized_scopes": kwargs.get("scopes") or []}
    try:
        refreshed = oauth_token_broker.refresh_google_access_token(account)
    finally:
        oauth_token_broker.get_secret = original_get
        oauth_token_broker.put_secret = original_put
        oauth_token_broker.provider_credentials = original_creds
        oauth_token_broker.urlopen = original_open
        oauth_token_broker.upsert_official_account = original_upsert
    assert refreshed["ok"] is True
    assert saved["oauth.ACC-GSC-TEST.access_token"] == "fresh-access"
    assert "refresh-secret" not in json.dumps(refreshed, ensure_ascii=False)

    geo_validation.bootstrap_question_set(force=True)
    geo_validation.set_decision({"mission_id": "MISSION-PHASE1-50", "daily_test_limit": 10})
    formal_batch = geo_api._prepare_browser_task({
        "limit": 50, "formal_50_batch": True, "platform": "chatgpt_web",
    })
    queue = geo_validation.queue_summary()
    assert queue["total"] == 50, queue
    assert formal_batch["claim"]["task"]["state"] == "running", formal_batch
    assert geo_validation.decision()["daily_test_limit"] == 50

    geo_core = (SOURCE / "core" / "geo_validation.py").read_text(encoding="utf-8")
    geo_ui = (SOURCE / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    seo_ui = (SOURCE / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    installer = (ROOT / "04_Build" / "installer" / "Kazuizhi_AI_V2.0.0_Beta_Setup.iss").read_text(encoding="utf-8")
    for marker in ("evidence_completeness", "retest_coverage", "phase2_not_connected"):
        assert marker in geo_core, marker
    for marker in ("被提及", "被推荐", "被引用", "24h复测", "72h复测", "7天复测", "准备剩余正式50问"):
        assert marker in geo_ui, marker
    for marker in ("最近真实成功", "最近真实失败", "已配置·待真实提交"):
        assert marker in seo_ui, marker
    assert "Install-KazuizhiPhase1Supervisor.ps1" in installer
    assert "[UninstallRun]" in installer
    print("PASS: Phase-1 continuity, Google refresh, truthful channels and GEO evidence gates")


if __name__ == "__main__":
    main()
