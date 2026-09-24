"""R8-12.2 regression: local-first Mission -> video recovery -> safe device staging.

This test deliberately keeps realtime ChatGPT absent. Routine Mission work must
continue locally, old account UI must stay retired, and real-device dry-run must
never cross the final publication truth gate.
"""
from __future__ import annotations

import copy
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def check_local_first_video_recovery():
    from promotion import local_mission_planner as planner
    from promotion import content_factory as cf

    state = {
        "campaigns": [{
            "id": "KZ-LOCAL-001", "region": "涟水县", "service": "水电安装维修",
            "title": "涟水水电维修本地验证", "goal": "真实咨询",
            "source_type": "legacy_upgrade",
        }],
        "videos": [{
            "id": "VIDEO-STUCK-001", "campaign_id": "KZ-LOCAL-001",
            "status": "异常待处理",
            "chatgpt_handoff": {"kind": "content_production", "phase": "retry_exhausted", "retry_count": 3},
            "production_plan": None,
            "candidates": [],
        }],
        "publication_plans": [], "receipts": [],
    }
    ops = {
        "active_mission_id": "MISSION-STABLE-001",
        "missions": [{
            "mission_id": "MISSION-STABLE-001", "growth_id": "KZ-LOCAL-001", "state": "active",
            "last_chatgpt_decision": {"action": "create_mission"},
        }],
    }
    original_read = planner.read_json
    original_load, original_save = cf._load, cf._save
    original_assets = cf._campaign_assets
    try:
        planner.read_json = lambda path, default=None: copy.deepcopy(ops if path == "ops/autonomous_ops.json" else default)
        cf._load = lambda: copy.deepcopy(state)
        def save(value):
            state.clear(); state.update(copy.deepcopy(value)); return value
        cf._save = save
        cf._campaign_assets = lambda data, campaign_id: []

        result = planner.recover_video("VIDEO-STUCK-001")
        assert result and result["video_id"] == "VIDEO-STUCK-001"
        assert result["status"] == "等待生产"
        assert len(state["videos"]) == 1, "local fallback duplicated the existing video"
        video = state["videos"][0]
        assert video["production_plan"]
        assert video["plan_source"] == "local_autonomy_under_active_mission"
        assert video["retry_count"] == 0
        assert video["bottleneck"] is None
        assert video["chatgpt_handoff"]["phase"] == "local_autonomy_plan"

        video["status"] = "异常待处理"
        video["candidates"] = []
        video["chatgpt_handoff"] = {"kind": "content_production", "phase": "retry_exhausted"}
        second = planner.recover_video("VIDEO-STUCK-001")
        assert second and second["video_id"] == "VIDEO-STUCK-001"
        assert len(state["videos"]) == 1
        assert state["videos"][0]["status"] == "等待生产"
    finally:
        planner.read_json = original_read
        cf._load, cf._save = original_load, original_save
        cf._campaign_assets = original_assets


def check_optional_chatgpt_contract():
    source = (SOURCE / "promotion" / "chatgpt_handoff_watchdog.py").read_text(encoding="utf-8")
    for token in (
        "authorized_mission_runs_local_first",
        "local_autonomy_retry",
        "实时ChatGPT为可选增强",
        "Mission自治任务不会走到这里",
        "_recover_authorized_local_qc",
    ):
        assert token in source, f"missing local-first watchdog contract: {token}"
    assert "非Mission授权任务的ChatGPT请求连续重发仍未返回" in source


def check_safe_douyin_device_staging():
    from integrations import douyin_dry_run_executor as executor

    runtime = {
        "devices": {
            "ELE-AL00": {
                "current_task": {
                    "task_id": "DRYRUN-PLAN-001", "kind": "douyin_publish_dry_run",
                    "plan_id": "PLAN-001", "video_id": "VIDEO-001", "campaign_id": "KZ-001",
                    "account_id": "ACC-DY-001", "account_asset_id": "ACC-DY-001",
                    "device_asset_id": "DEV-ELE-AL00", "adb_device_id": "ELE-AL00",
                    "status": "queued", "stage": "等待真机干跑",
                    "final_publish_allowed": False, "publishes_content": False,
                }
            }
        }
    }
    commands = []
    with tempfile.TemporaryDirectory() as temp:
        media = Path(temp) / "FINAL.mp4"
        media.write_bytes(b"0" * (16 * 1024))
        factory = {
            "videos": [{
                "id": "VIDEO-001", "campaign_id": "KZ-001",
                "approved_at": "2026-09-24T10:00:00+08:00", "review": {"decision": "确认发布"},
                "candidates": [{"id": "CUT-001", "local_path": str(media)}],
            }]
        }

        original_read, original_write = executor.read_json, executor.write_json
        original_load = executor.cf._load
        original_scan = executor.android_device.scan_and_sync
        original_run = executor.android_device._run
        original_audit = executor.android_device._append_audit
        try:
            executor.read_json = lambda path, default=None: copy.deepcopy(runtime)
            def write(path, value):
                runtime.clear(); runtime.update(copy.deepcopy(value)); return value
            executor.write_json = write
            executor.cf._load = lambda: copy.deepcopy(factory)
            executor.android_device.scan_and_sync = lambda: {
                "devices": [{"device_id": "ELE-AL00", "connected": True, "screen_state": "awake"}]
            }
            executor.android_device._run = lambda args, timeout=8, binary=False: commands.append(list(args)) or "ok"
            executor.android_device._append_audit = lambda event: None

            result = executor.run_pending(limit=1)
            assert result["processed"] == 1
            assert result["publishes_content"] is False
            task = runtime["devices"]["ELE-AL00"]["current_task"]
            assert task["status"] == "ready_for_composer"
            assert task["stage"] == "真实成片已上机，抖音已打开"
            assert task["final_publish_allowed"] is False
            assert task["publishes_content"] is False
            assert any("push" in command for command in commands)
            assert any("com.ss.android.ugc.aweme" in command for command in commands)

            command_count = len(commands)
            second = executor.run_pending(limit=1)
            assert second["processed"] == 0
            assert len(commands) == command_count
        finally:
            executor.read_json, executor.write_json = original_read, original_write
            executor.cf._load = original_load
            executor.android_device.scan_and_sync = original_scan
            executor.android_device._run = original_run
            executor.android_device._append_audit = original_audit


def check_legacy_account_owner_surface_retired():
    hotfix = (SOURCE / "web" / "r8_11_execution_tab_hotfix.js").read_text(encoding="utf-8")
    bridge = (SOURCE / "web" / "r8_12_account_center_bridge.js").read_text(encoding="utf-8")
    assert "const PAGES = new Set(['dashboard','content','search','device','conversion','health'])" in hotfix
    assert "retireLegacyAccountSurface" in hotfix
    assert "#account-form" in hotfix
    assert "page === 'accounts'" in hotfix
    assert "KZR812AccountCenter" in hotfix
    assert "/r8_12_account_center.html?embed=1" in bridge
    assert "stopImmediatePropagation" in bridge


def check_runtime_wires_safe_executor():
    run = (SOURCE / "run.py").read_text(encoding="utf-8")
    assert "douyin_dry_run_executor" in run
    assert run.count("run_pending_douyin_dry_runs(limit=1)") >= 2
    executor = (SOURCE / "integrations" / "douyin_dry_run_executor.py").read_text(encoding="utf-8")
    for token in ("ready_for_composer", "final_publish_allowed", "publishes_content", "Content/Post ID + URL / Receipt"):
        assert token in executor
    assert "input tap" not in executor, "safe staging executor must not click platform publish controls"


def main():
    check_local_first_video_recovery()
    check_optional_chatgpt_contract()
    check_safe_douyin_device_staging()
    check_legacy_account_owner_surface_retired()
    check_runtime_wires_safe_executor()
    print("PASS: R8-12.2 local-first Mission recovery, optional ChatGPT, retired legacy account UI and safe Douyin staging verified.")


if __name__ == "__main__":
    main()
