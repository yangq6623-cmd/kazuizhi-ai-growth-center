from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from integrations.business_data import ENDPOINT, snapshot_from_remote, validate_remote_summary


def fixture():
    return {
        "ok": True,
        "source": "Kazuizhi production SQLServer + WeChat Mini Program Analytics / aggregate-only / SELECT-only",
        "as_of": "2026-09-17T20:00:00+08:00",
        "window": {"today_local": "2026-09-17"},
        "users": {"total": 120, "new_today": 3},
        "orders": {"total": 50, "today": 2, "open": 4, "completed": 40, "cancelled": 3, "refunded": 2, "closed": 1},
        "technicians": {"total": 20, "approved": 17, "pending_review": 2, "active": 10},
        "partners": {"total": 8, "approved": 7, "pending_review": 1, "active": 4},
        "regions": [{"name": "涟水县", "count": 30}],
        "services": [{"name": "水电维修", "count": 12}],
        "promotion": {"event_records": 6, "partner_attributed_orders": 9},
        "mini_program": {
            "status": "ok", "ref_date": "20260916", "visit_uv": 88,
            "visit_pv": 140, "session_cnt": 95, "visit_uv_new": 12,
        },
        "funnel": {"mini_program_visits": 88, "repair_requests": 5, "leads": 4},
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
    assert snapshot["mini_program_visits"] == 88
    assert snapshot["repair_requests"] == 5
    assert snapshot["leads"] == 4
    assert snapshot["new_users"] == 3
    assert snapshot["new_orders"] == 2
    assert snapshot["by_region"]["涟水县"] == 30
    assert snapshot["by_skill"]["水电维修"] == 12
    assert "phone" not in snapshot

    no_wechat = fixture()
    no_wechat["mini_program"] = {"status": "unavailable", "ref_date": "20260916", "visit_uv": None}
    no_wechat["funnel"] = {"mini_program_visits": None, "repair_requests": 5, "leads": 4}
    clean_no_wechat = validate_remote_summary(no_wechat)
    snapshot_no_wechat = snapshot_from_remote(clean_no_wechat)
    assert snapshot_no_wechat["mini_program_visits"] is None
    assert snapshot_no_wechat["repair_requests"] == 5
    assert snapshot_no_wechat["leads"] == 4

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

    analytics_js = (SOURCE / "web" / "analytics.js").read_text(encoding="utf-8")
    assert "核心经营分析" in analytics_js
    assert "核心经营数据完整度" in analytics_js
    assert "小程序访问UV（最近完整日）" in analytics_js
    assert "今日维修需求" in analytics_js
    assert "今日有效线索" in analytics_js
    assert "累计已完成订单" in analytics_js
    assert "累计取消订单" in analytics_js
    assert "不跨窗口计算虚假转化率" in analytics_js
    for hidden_id in ("technician-supply", "leader-promotion", "channel-effect"):
        assert hidden_id in analytics_js

    print("PASS: live business source ingests verified core funnel metrics and keeps focused truthful analytics")


if __name__ == "__main__":
    main()
