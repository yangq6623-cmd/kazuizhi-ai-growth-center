from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from integrations.business_data import ENDPOINT, snapshot_from_remote, validate_remote_summary


def fixture():
    return {
        "ok": True,
        "source": "Kazuizhi production SQLServer / dbo.KzJsonDocuments / SELECT-only",
        "as_of": "2026-09-17T20:00:00+08:00",
        "window": {"today_local": "2026-09-17"},
        "users": {"total": 120, "new_today": 3},
        "orders": {"total": 50, "today": 2, "open": 4, "completed": 40, "cancelled": 3, "refunded": 2, "closed": 1},
        "technicians": {"total": 20, "approved": 17, "pending_review": 2, "active": 10},
        "partners": {"total": 8, "approved": 7, "pending_review": 1, "active": 4},
        "regions": [{"name": "涟水县", "count": 30}],
        "services": [{"name": "水电维修", "count": 12}],
        "promotion": {"event_records": 6, "partner_attributed_orders": 9},
        "data_quality": {
            "verified": True, "read_only": True, "write_operations": 0,
            "required_documents_present": 4, "required_documents_total": 4,
            "missing_documents": [], "contains_personal_data": False,
        },
    }


def main():
    assert ENDPOINT == "https://kazuizhi.com/ai-business-summary.ashx"
    clean = validate_remote_summary(fixture())
    snapshot = snapshot_from_remote(clean)
    assert snapshot["new_users"] == 3
    assert snapshot["new_orders"] == 2
    assert snapshot["by_region"]["涟水县"] == 30
    assert snapshot["by_skill"]["水电维修"] == 12
    assert "phone" not in snapshot

    unsafe = fixture()
    unsafe["phone"] = "13800000000"
    try:
        validate_remote_summary(unsafe)
    except ValueError:
        pass
    else:
        raise AssertionError("sensitive business field was not rejected")

    writable = fixture()
    writable["data_quality"] = dict(writable["data_quality"])
    writable["data_quality"]["write_operations"] = 1
    try:
        validate_remote_summary(writable)
    except ValueError:
        pass
    else:
        raise AssertionError("write-enabled business source was not rejected")

    print("PASS: live business source is fixed HTTPS, aggregate-only and SELECT-only")


if __name__ == "__main__":
    main()
