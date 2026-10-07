from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from integrations import wechat_mini_program as wx
from integrations import business_data


def main():
    calls = []
    def fake_request(url, payload=None):
        calls.append((url, payload))
        if "cgi-bin/token" in url:
            return {"access_token": "temporary-token"}
        return {"list": [{"ref_date": "20260927", "visit_uv": 88, "visit_pv": 140,
                           "session_cnt": 95, "visit_uv_new": 12}]}
    original = wx._request_json
    wx._request_json = fake_request
    try:
        summary = wx._fetch_summary({"app_id": "wx1234567890", "app_secret": "a" * 32})
    finally:
        wx._request_json = original
    assert summary["status"] == "ok"
    assert summary["visit_uv"] == 88
    assert summary["visit_pv"] == 140
    assert len(calls) == 2
    assert "getweanalysisappiddailyvisittrend" in calls[1][0]
    assert calls[1][1]["begin_date"] == calls[1][1]["end_date"]
    assert "access_token=temporary-token" in calls[1][0]
    assert "AppSecret" not in str(summary)

    # An already connected production Mini Program must not be rendered as
    # "not configured" just because the later optional direct WeChat analytics
    # credential file is absent.
    inherited = business_data._effective_wechat_status(
        {"mini_program": {"status": "ok", "ref_date": "20261007", "visit_uv": 66, "visit_pv": 120, "session_cnt": 80, "visit_uv_new": 9}},
        True,
        {"status": "not_configured", "has_credentials": False, "summary": {}},
    )
    assert inherited["status"] == "connected", inherited
    assert inherited["source_mode"] == "server_aggregate", inherited
    assert inherited["summary"]["visit_uv"] == 66, inherited
    assert inherited["has_credentials"] is False
    assert "无需重复填写" in inherited["message"]

    business_only = business_data._effective_wechat_status(
        {"mini_program": {"status": "wechat_error"}},
        True,
        {"status": "not_configured", "has_credentials": False, "summary": {}},
    )
    assert business_only["status"] == "business_connected", business_only
    assert business_only["business_connected"] is True
    assert "不需要重新接入小程序" in business_only["message"]

    analytics = (SOURCE / "web" / "analytics.js").read_text(encoding="utf-8")
    for marker in ("复用既有业务接入", "高级：仅在需要直接拉取微信访问统计时配置 AppID / AppSecret", "小程序业务已经接入"):
        assert marker in analytics, marker
    print("PASS: WeChat Mini Program connector reuses existing production integration and keeps direct analytics optional")


if __name__ == "__main__":
    main()
