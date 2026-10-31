"""HTTP/runtime bridge for the unified R7 <-> ChatGPT <-> R8 Mission loop."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from core import autonomous_ops
from promotion import content_factory as cf

_INSTALLED = False
_ORIGINAL = {}


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 64 * 1024:
        raise ValueError("请求大小不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


def _with_mission_context(limit=20):
    payload = _ORIGINAL["pending_chatgpt_handoff"](limit)
    for item in payload.get("items", []):
        context = autonomous_ops.mission_context_for_growth(item.get("campaign_id"))
        if context:
            # mission_context intentionally contains r7_context plus owner goal,
            # Mission identity and verified R8 feedback as one decision envelope.
            item["mission_context"] = context
            item["instruction"] = (
                str(item.get("instruction") or "") +
                " 同时读取mission_context中的老板目标、R7经理判断、区域策略与上一轮执行结果；"
                "保持同一Mission连续决策，执行结果必须回流R7复盘。"
            ).strip()
    return payload


def _sync_after(name, func):
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        try:
            autonomous_ops.sync_from_runtime(autostart=False)
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            pass
        return result
    wrapped.__name__ = getattr(func, "__name__", name)
    return wrapped


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    _ORIGINAL["pending_chatgpt_handoff"] = cf.pending_chatgpt_handoff
    cf.pending_chatgpt_handoff = _with_mission_context

    # Turn important R8 state transitions into Mission events immediately instead
    # of waiting for the periodic scheduler snapshot.
    names = (
        "create_campaign", "create_video", "apply_chatgpt_plan", "record_candidate",
        "apply_chatgpt_qc", "review_video", "create_publish_plan", "record_receipt",
    )
    for name in names:
        func = getattr(cf, name, None)
        if callable(func):
            _ORIGINAL[name] = func
            setattr(cf, name, _sync_after(name, func))

    # Repoint server aliases captured at import time to the final wrapped functions.
    alias_map = {
        "factory_create_campaign": "create_campaign",
        "factory_create_video": "create_video",
        "factory_apply_chatgpt_plan": "apply_chatgpt_plan",
        "factory_record_candidate": "record_candidate",
        "factory_apply_chatgpt_qc": "apply_chatgpt_qc",
        "factory_review_video": "review_video",
        "factory_create_publish_plan": "create_publish_plan",
        "factory_record_receipt": "record_receipt",
    }
    for alias, name in alias_map.items():
        func = getattr(cf, name, None)
        if callable(func) and hasattr(server, alias):
            setattr(server, alias, func)

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/autonomous-ops":
            try:
                handler._json_ok(autonomous_ops.snapshot(sync=True))
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
                handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path in {"/api/autonomous-ops/goal", "/api/autonomous-ops/mission/activate"}:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                if path.endswith("/goal"):
                    result = autonomous_ops.set_owner_goal(payload)
                else:
                    result = autonomous_ops.activate_mission(payload)
                handler._json_ok(result)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_autonomous_ops_patched = True
    _INSTALLED = True


install()
