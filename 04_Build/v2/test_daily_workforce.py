import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-workforce-"))
os.environ["LOCALAPPDATA"] = str(sandbox)

try:
    from core.daily_workforce import DAILY_TEMPLATE, ensure_daily_workforce
    from core.r7_engine import list_jobs

    first = ensure_daily_workforce()
    second = ensure_daily_workforce()
    jobs = [job for job in list_jobs()["items"] if job.get("schedule_source") == "daily_workforce"]

    if first["planned"] < 18:
        raise AssertionError(f"Daily plan is too sparse: {first}")
    if first["created"] != first["planned"]:
        raise AssertionError(f"Initial schedule did not create every planned job: {first}")
    if second["created"] != 0:
        raise AssertionError(f"Daily schedule is not idempotent: {second}")
    if len(jobs) != first["planned"]:
        raise AssertionError(f"Scheduled job count mismatch: {len(jobs)} vs {first['planned']}")

    expected_agents = {
        "市场情报员", "SEO/GEO 增长员", "内容运营员", "社媒运营员",
        "短视频运营员", "本地增长员", "用户转化员", "数据复盘员",
    }
    actual_agents = {job.get("agent") for job in jobs}
    missing = expected_agents - actual_agents
    if missing:
        raise AssertionError(f"AI employee schedule missing roles: {sorted(missing)}")

    for job in jobs:
        if job.get("risk") != "non_financial" or job.get("execution") != "autonomous":
            raise AssertionError(f"Unsafe scheduled job: {job}")
        if job.get("state") != "queued" or job.get("mode") != "local":
            raise AssertionError(f"Scheduled job is not queued locally: {job}")
        if not job.get("due_at") or not job.get("schedule_time"):
            raise AssertionError(f"Scheduled job missing exact execution time: {job}")

    times = [hhmm for hhmm, *_ in DAILY_TEMPLATE]
    if times != sorted(times):
        raise AssertionError("Daily workforce template is not time ordered")

    patch = (SRC / "web" / "r7_manager_patch.js").read_text(encoding="utf-8")
    required_ui = (
        "r7FullDateTime", "data-dismiss-human", "r7-today-working",
        "r7-today-queued", "r7-today-completed", "r7-today-human",
        "data-filter=\"queued\"", "完整记录仍保留",
    )
    for token in required_ui:
        if token not in patch:
            raise AssertionError(f"Manager UX patch missing contract token: {token}")

    print("PASS: full-day 8-role AI workforce schedule, idempotency, finance guardrail, timestamps, clickable KPI filters and dismissible finance reminders")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
