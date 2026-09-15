"""Verified aggregate business metrics and five operational analyses.

This module never treats public search signals or disconnected zero placeholders as
business results. A snapshot is usable only when it includes a source and timestamp.
"""

import json
import os
from pathlib import Path

from core.storage import now_iso, read_json, write_json


SCALAR_FIELDS = (
    "mini_program_visits", "repair_requests", "new_orders", "completed_orders",
    "cancelled_orders", "new_users", "new_technicians", "approved_technicians",
    "active_technicians", "new_leaders", "active_leaders", "leader_referrals",
    "leader_orders", "published_content", "real_interactions", "leads",
    "technician_inquiries", "review_count",
)
MAP_FIELDS = ("by_region", "by_skill", "channel_visits", "channel_orders")
NESTED_MAP_FIELDS = ("by_region_skill",)
META_FIELDS = ("as_of", "source", "window")
ALLOWED_FIELDS = set(SCALAR_FIELDS + MAP_FIELDS + NESTED_MAP_FIELDS + META_FIELDS + ("verified_at",))
FORBIDDEN_PARTS = (
    "phone", "mobile", "address", "openid", "unionid", "id_card", "password",
    "secret", "token", "adminkey", "admin_key", "payment", "refund", "bank",
)


def _clean_number(value, field):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field} must be a non-negative number or null")
    return value


def _clean_map(value, field, nested=False):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object or null")
    cleaned = {}
    for key, item in value.items():
        label = str(key).strip()
        if not label or len(label) > 80:
            raise ValueError(f"{field} contains an invalid label")
        if any(part in label.lower() for part in FORBIDDEN_PARTS):
            raise ValueError(f"{field} contains a sensitive or financial label")
        cleaned[label] = _clean_map(item, f"{field}.{label}") if nested else _clean_number(item, f"{field}.{label}")
    return cleaned


def validate_snapshot(payload):
    if not isinstance(payload, dict):
        raise ValueError("business snapshot must be an object")
    unknown = set(payload) - ALLOWED_FIELDS
    unsafe = [key for key in payload if any(part in key.lower() for part in FORBIDDEN_PARTS)]
    if unsafe:
        raise ValueError("sensitive or financial fields are not accepted")
    if unknown:
        raise ValueError("unsupported aggregate fields: " + ", ".join(sorted(unknown)))
    source = str(payload.get("source", "")).strip()
    as_of = str(payload.get("as_of", "")).strip()
    if not source or not as_of:
        raise ValueError("source and as_of are required for verified business data")
    clean = {"source": source[:120], "as_of": as_of[:80], "window": str(payload.get("window", "today"))[:40]}
    for field in SCALAR_FIELDS:
        if field in payload:
            clean[field] = _clean_number(payload[field], field)
    for field in MAP_FIELDS:
        if field in payload:
            clean[field] = _clean_map(payload[field], field)
    for field in NESTED_MAP_FIELDS:
        if field in payload:
            clean[field] = _clean_map(payload[field], field, nested=True)
    clean["verified_at"] = now_iso()
    return clean


def import_snapshot(payload):
    clean = validate_snapshot(payload)
    write_json("business/verified_snapshot.json", clean)
    return build_analytics(clean)


def _standard_paths():
    explicit = os.environ.get("KAZUIZHI_BUSINESS_METRICS_PATH")
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    paths = []
    if explicit:
        paths.append(Path(explicit))
    paths.extend([
        Path(r"C:\卡嘴子自动化\bridge\business_metrics.json"),
        local / "Kazuizhi-AI" / "data" / "business_metrics.json",
    ])
    return paths


def _read_external(path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return validate_snapshot(payload)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def current_snapshot():
    for path in _standard_paths():
        if path.is_file():
            snapshot = _read_external(path)
            if snapshot:
                snapshot["loaded_from"] = str(path)
                return snapshot
    saved = read_json("business/verified_snapshot.json", None)
    if saved:
        try:
            return validate_snapshot(saved)
        except ValueError:
            return None
    return None


def _rate(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return round(numerator * 100 / denominator, 2)


def _module(name, values, rates=None, breakdown=None):
    available = any(value is not None for value in values.values())
    return {
        "name": name,
        "status": "verified" if available else "not_connected",
        "values": values,
        "rates": rates or {},
        "breakdown": breakdown or {},
    }


def build_analytics(snapshot=None):
    snapshot = snapshot or current_snapshot()
    if not snapshot:
        empty = {
            key: _module(label, {}) for key, label in (
                ("user_growth", "用户增长分析"),
                ("order_conversion", "订单转化分析"),
                ("technician_supply", "师傅资源分析"),
                ("leader_promotion", "团长推广分析"),
                ("channel_effect", "渠道效果分析"),
            )
        }
        return {
            "status": "not_connected",
            "message": "真实经营数据尚未接入，当前不展示占位 0 或推测数字。",
            "source": None,
            "as_of": None,
            "truth_rule": "公开市场信号只用于需求研究，不计为访问、用户、订单或成交。",
            "modules": empty,
        }
    user_values = {key: snapshot.get(key) for key in ("mini_program_visits", "repair_requests", "new_users", "leads")}
    order_values = {key: snapshot.get(key) for key in ("repair_requests", "new_orders", "completed_orders", "cancelled_orders")}
    technician_values = {key: snapshot.get(key) for key in ("new_technicians", "approved_technicians", "active_technicians", "technician_inquiries")}
    leader_values = {key: snapshot.get(key) for key in ("new_leaders", "active_leaders", "leader_referrals", "leader_orders")}
    channels = []
    channel_visits = snapshot.get("channel_visits") or {}
    channel_orders = snapshot.get("channel_orders") or {}
    for channel in sorted(set(channel_visits) | set(channel_orders)):
        visits = channel_visits.get(channel)
        orders = channel_orders.get(channel)
        channels.append({"channel": channel, "visits": visits, "orders": orders, "conversion_pct": _rate(orders, visits)})
    modules = {
        "user_growth": _module("用户增长分析", user_values, {
            "visit_to_request_pct": _rate(snapshot.get("repair_requests"), snapshot.get("mini_program_visits")),
            "request_to_lead_pct": _rate(snapshot.get("leads"), snapshot.get("repair_requests")),
        }),
        "order_conversion": _module("订单转化分析", order_values, {
            "request_to_order_pct": _rate(snapshot.get("new_orders"), snapshot.get("repair_requests")),
            "order_to_complete_pct": _rate(snapshot.get("completed_orders"), snapshot.get("new_orders")),
            "order_cancel_pct": _rate(snapshot.get("cancelled_orders"), snapshot.get("new_orders")),
        }),
        "technician_supply": _module("师傅资源分析", technician_values, {
            "inquiry_to_approval_pct": _rate(snapshot.get("approved_technicians"), snapshot.get("technician_inquiries")),
        }, {"by_region": snapshot.get("by_region"), "by_skill": snapshot.get("by_skill"), "by_region_skill": snapshot.get("by_region_skill")}),
        "leader_promotion": _module("团长推广分析", leader_values, {
            "referral_to_order_pct": _rate(snapshot.get("leader_orders"), snapshot.get("leader_referrals")),
        }),
        "channel_effect": _module("渠道效果分析", {"channel_count": len(channels) if channels else None}, breakdown={"channels": channels}),
    }
    return {
        "status": "verified",
        "message": "已读取带来源和时间的聚合经营快照。",
        "source": snapshot.get("source"),
        "as_of": snapshot.get("as_of"),
        "window": snapshot.get("window", "today"),
        "truth_rule": "只显示已验证聚合数据；不接收手机号、地址、身份、密钥或资金明细。",
        "modules": modules,
    }


def summary_snapshot():
    snapshot = current_snapshot()
    if not snapshot:
        return {}
    mapping = {
        "orders": "new_orders",
        "users": "new_users",
        "masters": "active_technicians",
        "leaders": "active_leaders",
        "promotion": "published_content",
    }
    return {target: snapshot.get(source) for target, source in mapping.items() if snapshot.get(source) is not None}


def import_template():
    return {
        "as_of": "YYYY-MM-DD HH:mm:ss",
        "source": "server-readonly-export",
        "window": "today",
        **{field: None for field in SCALAR_FIELDS},
        **{field: None for field in MAP_FIELDS + NESTED_MAP_FIELDS},
    }
