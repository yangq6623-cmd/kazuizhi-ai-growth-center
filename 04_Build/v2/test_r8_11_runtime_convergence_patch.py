from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(ROOT))

from promotion.r8_11_runtime_convergence_patch import can_resume_publish, select_foreground_video


def main():
    growth = "KZ-TEST"
    approved = {
        "id": "VIDEO-OLD",
        "campaign_id": growth,
        "status": "等待账号",
        "approved_at": "2026-09-24T10:00:00+08:00",
        "review": {"decision": "确认发布"},
        "requested_at": "2026-09-24T09:00:00+08:00",
    }
    duplicate = {
        "id": "VIDEO-NEW",
        "campaign_id": growth,
        "status": "等待ChatGPT策划",
        "approved_at": None,
        "review": None,
        "requested_at": "2026-09-24T10:30:00+08:00",
    }

    assert can_resume_publish(approved) is True
    assert can_resume_publish(duplicate) is False
    assert select_foreground_video([duplicate, approved], growth)["id"] == "VIDEO-OLD"

    not_approved = dict(approved, approved_at=None)
    assert can_resume_publish(not_approved) is False

    other_growth = dict(duplicate, id="VIDEO-OTHER", campaign_id="KZ-OTHER")
    assert select_foreground_video([other_growth], growth) is None

    print("R8-11 runtime convergence regression passed")


if __name__ == "__main__":
    main()
