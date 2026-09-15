"""Create a daily summary without inventing unavailable business metrics."""

from datetime import date
from analytics.business_metrics import summary_snapshot
from core.storage import now_iso, read_json, write_json


METRICS = ("orders", "users", "revenue", "masters", "leaders", "promotion")


def build_summary(snapshot=None):
    snapshot = summary_snapshot() if snapshot is None else snapshot
    verified = {key: snapshot[key] for key in METRICS if snapshot.get(key) is not None}
    missing = [key for key in METRICS if key not in verified]
    if verified:
        headline = "已根据本机已验证数据生成今日运营摘要。"
        status = "partial" if missing else "verified"
    else:
        headline = "真实经营数据尚未接入，今日不展示推测数字。"
        status = "not_connected"
    saved = read_json("summaries/today.json", {})
    return {
        "date": str(date.today()),
        "status": status,
        "headline": headline,
        "verified_metrics": verified,
        "missing_metrics": missing,
        "data_policy": "只使用已验证的本机经营数据；公开市场信号不计为订单或成交。",
        "completed_items": saved.get("completed_items", []),
        "saved_at": saved.get("saved_at"),
    }


def save_summary(items):
    clean = [str(item).strip() for item in items if str(item).strip()][:100]
    if not clean:
        raise ValueError("completed_items must not be empty")
    write_json("summaries/today.json", {"date": str(date.today()), "saved_at": now_iso(), "completed_items": clean})
    return build_summary()
