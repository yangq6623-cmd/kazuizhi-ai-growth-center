import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core.storage import read_json
from integrations import android_device
from promotion import content_factory
from promotion import content_factory_v2_extensions  # noqa: F401 - installs publish semantics
from promotion.publish_orchestrator import run_publish_planning


def main():
    with tempfile.TemporaryDirectory() as temp:
        old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        original_scan = android_device.scan_and_sync
        try:
            android_device.scan_and_sync = lambda: {
                "devices": [{
                    "device_id": "ADB-REAL-001",
                    "connected": True,
                    "model": "ELE-AL00",
                    "screen_state": "awake",
                }],
                "primary_device_id": "ADB-REAL-001",
                "adb": {"found": True, "status": "ready"},
            }
            content_factory._save({
                "schema_version": 2,
                "campaigns": [{
                    "id": "KZ-DRYRUN-001",
                    "region": "涟水县",
                    "service": "水电安装维修",
                    "title": "涟水县水电安装维修第一轮本地增长验证",
                    "goal": "获得可追溯的真实咨询或订单",
                    "status": "视频生产中",
                }],
                "assets": [],
                "videos": [{
                    "id": "VIDEO-DRYRUN-001",
                    "campaign_id": "KZ-DRYRUN-001",
                    "status": "已授权发布",
                    "approved_at": "2026-09-24T04:00:00+08:00",
                    "review": {"decision": "确认发布", "reviewed_at": "2026-09-24T04:00:00+08:00"},
                    "target_platforms": ["抖音"],
                    "caption_direction": "涟水县水电安装维修需求发布说明",
                    "cta": "通过小程序提交需求，等待师傅报价",
                    "production_plan": {
                        "titles": ["涟水县水电安装维修需求怎么发布"],
                        "target_platforms": ["抖音"],
                        "platform_adaptation": {
                            "抖音": {
                                "title": "涟水县水电安装维修需求怎么发布",
                                "caption": "先把问题、位置和方便上门时间说明白，再通过卡嘴子提交需求。",
                                "schedule_hint": "真机干跑通过后再由系统选择发布时间",
                            }
                        },
                        "storyboard": [],
                    },
                    "candidates": [{
                        "id": "CUT-DRYRUN-001",
                        "exists": True,
                        "technical_qc": {"passed": True},
                        "source_summary": [],
                    }],
                    "retry_count": 0,
                }],
                "accounts": [{
                    "id": "ACCOUNT-DOUYIN-001",
                    "platform": "抖音",
                    "account_name": "卡嘴子本地服务维修",
                    "region": "涟水县",
                    "service": "水电安装维修",
                    "connection_status": "已验证可发布",
                    "device_id": "ADB-REAL-001",
                    "daily_limit": 1,
                    "preferred_windows": [],
                }],
                "publication_plans": [],
                "receipts": [],
                "feedback": [],
            })

            first = run_publish_planning(limit=10)
            assert first["processed"] == 1
            data = content_factory._load()
            assert len(data["publication_plans"]) == 1
            plan = data["publication_plans"][0]
            assert plan["platform"] == "抖音"
            assert plan["status"] == "等待最佳时间"
            video = data["videos"][0]
            assert video["status"] == "等待最佳时间"
            assert video["publish_planning"]["douyin_dry_run"]["queued"] is True
            assert data["receipts"] == []

            runtime = read_json(android_device.RUNTIME_PATH, {})
            task = runtime["devices"]["ADB-REAL-001"]["current_task"]
            assert task["kind"] == "douyin_publish_dry_run"
            assert task["plan_id"] == plan["id"]
            assert task["video_id"] == "VIDEO-DRYRUN-001"
            assert task["status"] == "queued"
            assert task["final_publish_allowed"] is False
            assert task["publishes_content"] is False

            second = run_publish_planning(limit=10)
            data2 = content_factory._load()
            assert len(data2["publication_plans"]) == 1, "planning must be idempotent"
            runtime2 = read_json(android_device.RUNTIME_PATH, {})
            task2 = runtime2["devices"]["ADB-REAL-001"]["current_task"]
            assert task2["plan_id"] == plan["id"]
            assert second["processed"] == 1
            assert data2["receipts"] == [], "dry run must never fabricate a publication receipt"
        finally:
            android_device.scan_and_sync = original_scan
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local

    print("PASS: owner-approved Douyin plan becomes one idempotent real-device dry-run task and never counts as published.")


if __name__ == "__main__":
    main()
