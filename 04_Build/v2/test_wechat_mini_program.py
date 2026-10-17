from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from integrations import wechat_mini_program as wx


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
    print("PASS: WeChat Mini Program connector only accepts aggregate daily visit data")


if __name__ == "__main__":
    main()
