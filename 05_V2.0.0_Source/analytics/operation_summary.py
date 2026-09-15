"""Create a daily summary without inventing unavailable business metrics."""

from datetime import date


METRICS = ("orders", "users", "revenue", "masters", "leaders", "promotion")


def build_summary(snapshot=None):
    snapshot = snapshot or {}
    verified = {key: snapshot[key] for key in METRICS if snapshot.get(key) is not None}
    missing = [key for key in METRICS if key not in verified]
    if verified:
        headline = "已根据本机已验证数据生成今日运营摘要。"
        status = "partial" if missing else "verified"
    else:
        headline = "真实经营数据尚未接入，今日不展示推测数字。"
        status = "not_connected"
    return {
        "date": str(date.today()),
        "status": status,
        "headline": headline,
        "verified_metrics": verified,
        "missing_metrics": missing,
        "data_policy": "只使用已验证的本机经营数据；公开市场信号不计为订单或成交。",
    }

