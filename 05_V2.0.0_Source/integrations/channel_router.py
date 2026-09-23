"""R8-11 channel routing contract.

This module turns the unified channel registry into truthful execution routes.
It does not bypass platform login, captcha, face verification, owner final
approval, or finance controls.  It also does not require any paid third-party
token service.
"""
from __future__ import annotations

from core.storage import now_iso
from integrations.channel_registry import snapshot as registry_snapshot


def _active_mission() -> dict:
    try:
        from core.mission_ledger import snapshot as ledger_snapshot
        return (ledger_snapshot().get("active_mission") or {})
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def build_routes() -> dict:
    registry = registry_snapshot()
    mission = _active_mission()
    video = mission.get("active_video") or {}
    candidate = video.get("candidate") or {}
    owner_approved = str(video.get("status") or "") in {"已授权发布", "等待账号", "等待最佳时间", "发布执行中", "已验证发布"}
    rows = []
    for channel in registry.get("channels", []):
        cid = channel.get("id")
        group = channel.get("group")
        if not mission:
            state = "waiting_mission"
            action = "等待 ChatGPT / 老板建立 Mission"
        elif group in {"short_video", "social_content"}:
            if not candidate.get("exists"):
                state = "waiting_content"
                action = "等待真实成片/内容候选"
            elif not owner_approved:
                state = "waiting_owner_approval"
                action = "老板审核通过后才能进入真实发布队列"
            elif not channel.get("external_verified"):
                state = "waiting_external_validation"
                action = "等待真实账号登录 + ADB 真机验证"
            else:
                state = "ready_for_dry_run"
                action = "进入真机干跑；最终发布仍需真实平台页面与回执验证"
        elif group == "search":
            state = "ready_for_content_route"
            action = "生成/更新 SEO-GEO 内容并等待真实抓取/收录证据"
        elif group == "owned":
            state = "ready_owned_route" if channel.get("external_verified") else "registered_pending_validation"
            action = "按自有站点/小程序能力写入可验证内容或经营数据链"
        else:
            state = "registered_manual_or_browser_route"
            action = "已进入统一路由；需要平台登录/规则确认时转人工或浏览器辅助"
        rows.append({
            "channel_id": cid,
            "name": channel.get("name"),
            "group": group,
            "route_state": state,
            "next_action": action,
            "software_route_ready": bool(channel.get("software_route_ready")),
            "external_verified": bool(channel.get("external_verified")),
            "paid_token_required": False,
            "human_gates": channel.get("human_gates") or [],
        })
    return {
        "schema": "kz.channel-routes.v1",
        "generated_at": now_iso(),
        "mission_id": mission.get("mission_id"),
        "growth_id": mission.get("growth_id"),
        "video_id": video.get("video_id"),
        "routes": rows,
        "summary": {
            "total": len(rows),
            "software_route_ready": sum(1 for x in rows if x.get("software_route_ready")),
            "ready_or_preparable": sum(1 for x in rows if x.get("route_state") in {"ready_for_dry_run", "ready_for_content_route", "ready_owned_route", "registered_manual_or_browser_route", "registered_pending_validation"}),
            "paid_token_required": 0,
        },
        "truth_rule": "路由已建立不等于外部平台已发布；真实发布必须有平台 Content ID + URL + Receipt。",
    }
