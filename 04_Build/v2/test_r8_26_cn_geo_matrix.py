"""Release gate for the five-platform domestic GEO baseline."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
TEST_ROOT = Path(tempfile.mkdtemp(prefix=".kz-cn-geo-", dir=ROOT))
atexit.register(shutil.rmtree, TEST_ROOT, True)
os.environ["LOCALAPPDATA"] = str(TEST_ROOT)

from core import geo_domestic_matrix, geo_validation, phase1_acceptance  # noqa: E402
from integrations import geo_browser_validation  # noqa: E402


def main():
    questions = geo_validation.question_set()["questions"]
    allocation = geo_domestic_matrix.assignments(questions)
    assert list(allocation) == [
        "doubao_web", "douyin_search_web", "deepseek_web", "qwen_web", "so360_ai_search",
    ]
    assert all(len(ids) == 10 for ids in allocation.values())
    assert len({qid for ids in allocation.values() for qid in ids}) == 50

    prepared = geo_domestic_matrix.prepare_missing(limit=50, mission_id="MISSION-CN-GEO50")
    assert prepared["created"] == 50, prepared
    assert prepared["matrix"]["completed"] == 0
    assert prepared["matrix"]["target"] == 50
    assert all(task.get("expected_platform") for task in prepared["tasks"])

    claim = geo_validation.claim_next_task({
        "real_external": True, "authorization_ready": True, "provider_ready": True,
        "provider": "deepseek_web", "test_method": "browser", "executor_id": "test-browser",
    })
    task = claim["task"]
    assert task["expected_platform"] == "deepseek_web", task
    try:
        geo_browser_validation.record_browser_result({
            "task_id": task["task_id"], "platform": "chatgpt_web",
            "session_url": "https://chatgpt.com/c/test", "raw_answer": "外部回答",
        })
        raise AssertionError("mismatched platform receipt must be rejected")
    except ValueError as error:
        assert "does_not_match" in str(error)

    receipt = geo_browser_validation.record_browser_result({
        "task_id": task["task_id"], "platform": "deepseek_web",
        "session_url": "https://chat.deepseek.com/a/chat/s/test", "raw_answer": "完整真实外部回答",
    })
    assert receipt["official_truth"] is True and receipt["evidence_level"] == "A"
    matrix = geo_domestic_matrix.snapshot(
        geo_validation.receipts(1000), questions, geo_validation.queue_summary()["tasks"],
    )
    assert matrix["completed"] == 1, matrix
    deepseek = next(row for row in matrix["platforms"] if row["platform"] == "deepseek_web")
    assert deepseek["completed"] == 1 and deepseek["target"] == 10
    slot = next(row for row in matrix["slots"] if row["platform"] == "deepseek_web" and row["question_id"] == task["question_id"])
    assert slot["state"] == "succeeded", slot
    assert slot["evidence_id"] == receipt["evidence_id"], slot
    assert slot["evidence_ref"], slot

    dashboard = geo_validation.dashboard()
    assert dashboard["domestic_matrix"]["completed"] == 1
    observed = phase1_acceptance.observe(
        runtime={"process": {"running": True, "pid": 1}, "health": "healthy", "workers": {}},
        search={}, geo=dashboard, supervisor={},
    )
    assert observed["geo_snapshot"]["formal_scope"] == "china_domestic_primary"
    assert observed["geo_snapshot"]["formal_ab_completed"] == 1

    browser = geo_browser_validation.status()
    ids = {row["id"] for row in browser["platforms"]}
    assert set(allocation).issubset(ids)
    assert browser["requires_api"] is False
    assert browser["automatic_after_login"] is False
    assert browser["automation_requires"] == "connected_authenticated_browser_agent"

    ui = (SOURCE / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    for marker in ("豆包", "抖音搜索", "DeepSeek", "通义千问", "360 AI 搜索", "准备剩余正式50问（国内五平台）", "formalReceipts", "item.evidence?'succeeded'"):
        assert marker in ui, marker
    print("PASS: domestic GEO 5x10 matrix, platform truth gate and no-API browser route")


if __name__ == "__main__":
    main()
