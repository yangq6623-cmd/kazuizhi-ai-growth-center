"""R8-24.1 truthful publish bridge for GEO Growth OS.

The GEO orchestrator may prepare QC_PASSED assets, but that is not a public
publication. This patch connects the existing guarded SEO public deployer to the
GEO operating loop. A page advances only when the deployer obtains a real public
HTTP/content/canonical/Schema/robots receipt. Missing deployment configuration is
shown as a technical blocker and never faked as success.
"""
from __future__ import annotations

from copy import deepcopy

from core import geo_growth_orchestrator as geo_growth
from integrations import seo_public_deployer

_INSTALLED = False
_ORIGINAL_RUN = geo_growth.run_once
_ORIGINAL_STATUS = geo_growth.status
_ORIGINAL_RETRY = geo_growth.retry_failed
_PUBLISH_BLOCKER_CODES = {
    "publish_connector_not_ready",
    "public_publish_verification_failed",
    "public_publish_deferred",
}


def _clear_publish_blockers(data):
    data["technical_blockers"] = [
        row for row in (data.get("technical_blockers") or [])
        if str(row.get("code") or "") not in _PUBLISH_BLOCKER_CODES
    ]
    return data


def _waiting_publish(data):
    return [
        row for row in (data.get("opportunities") or [])
        if row.get("state") == "waiting_publish" or row.get("asset_stage") == "QC_PASSED"
    ]


def _attempt_publish(force=False):
    data = geo_growth._load()
    geo_growth._sync_all(data)
    data = _clear_publish_blockers(data)
    waiting = _waiting_publish(data)
    connector = seo_public_deployer.status()

    if not waiting:
        geo_growth._save(data)
        return {
            "attempted": 0,
            "published": [],
            "failed": [],
            "skipped": True,
            "reason": "no_qc_passed_assets",
            "connector": connector,
        }

    if not connector.get("ready"):
        reason = str(connector.get("reason") or "真实发布连接器尚未就绪")
        geo_growth._record_blocker(
            data,
            "publish_connector_not_ready",
            f"{reason}；当前有 {len(waiting)} 条 GEO 资产已通过 QC，等待真实公网发布。",
            "GEO-PUBLISH-BRIDGE",
        )
        geo_growth._record_history(data, "publish_waiting_connector", {
            "waiting": len(waiting),
            "reason": reason,
            "truth": "QC_PASSED 不等于 PUBLISHED",
        })
        geo_growth._save(data)
        return {
            "attempted": 0,
            "published": [],
            "failed": [],
            "skipped": True,
            "reason": reason,
            "connector": connector,
        }

    try:
        result = seo_public_deployer.deploy_pending(limit=max(1, min(20, len(waiting))))
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        geo_growth._record_blocker(data, "public_publish_deferred", error, "GEO-PUBLISH-BRIDGE")
        geo_growth._save(data)
        return {
            "attempted": 0,
            "published": [],
            "failed": [{"reason": str(error)}],
            "skipped": False,
            "connector": connector,
        }

    published = list(result.get("published") or [])
    failed = list(result.get("failed") or [])
    if published:
        geo_growth._record_history(data, "public_publish_verified", {
            "published": deepcopy(published),
            "truth": "仅真实公网验证通过的页面计为 PUBLISHED",
        })
    for row in failed:
        asset_id = str(row.get("asset_id") or "")
        detail = str(row.get("reason") or "公网发布验证失败")
        public_url = str(row.get("public_url") or "")
        if public_url:
            detail = f"{detail} · {public_url}"
        geo_growth._record_blocker(data, "public_publish_verification_failed", detail, asset_id)

    geo_growth._save(data)
    refreshed = geo_growth._load()
    geo_growth._sync_all(refreshed)
    if published and not failed:
        _clear_publish_blockers(refreshed)
    geo_growth._save(refreshed)
    return {**result, "connector": seo_public_deployer.status()}


def run_once(force=False):
    result = _ORIGINAL_RUN(force=force)
    state = geo_growth._load()
    if not state.get("enabled") or state.get("paused"):
        return result

    publish_result = _attempt_publish(force=force)
    if publish_result.get("published"):
        # A second bounded sync pass advances newly verified PUBLISHED assets to
        # waiting_retest and schedules their truthful operating lifecycle.
        _ORIGINAL_RUN(force=False)
    if isinstance(result, dict):
        merged = dict(result)
        merged["publish_bridge"] = publish_result
        return merged
    return {"result": result, "publish_bridge": publish_result}


def status():
    snap = _ORIGINAL_STATUS()
    connector = seo_public_deployer.status()
    snap["publish_connector"] = {
        "configured": bool(connector.get("configured")),
        "enabled": bool(connector.get("enabled")),
        "ready": bool(connector.get("ready")),
        "mode": connector.get("mode") or "",
        "public_base_url": connector.get("public_base_url") or "",
        "reason": connector.get("reason") or "",
        "truth": connector.get("truth") or "",
    }

    waiting = int((snap.get("summary") or {}).get("waiting_publish") or 0)
    blockers = list(snap.get("technical_blockers") or [])
    if waiting and not connector.get("ready"):
        exists = any(row.get("code") == "publish_connector_not_ready" for row in blockers)
        if not exists:
            blockers.insert(0, {
                "code": "publish_connector_not_ready",
                "detail": f"{connector.get('reason') or '真实发布连接器尚未就绪'}；当前 {waiting} 条资产等待真实发布。",
                "item_id": "GEO-PUBLISH-BRIDGE",
                "blocking_scope": "subtask_only",
                "main_loop_continues": True,
            })
    snap["technical_blockers"] = blockers[:12]
    snap.setdefault("summary", {})["technical_blockers"] = len(blockers)
    return snap


def retry_failed():
    _ORIGINAL_RETRY()
    run_once(force=True)
    return status()


def install():
    global _INSTALLED
    if _INSTALLED or getattr(geo_growth, "_kz_r8_24_publish_bridge", False):
        return
    geo_growth.run_once = run_once
    geo_growth.status = status
    geo_growth.retry_failed = retry_failed
    geo_growth._kz_r8_24_publish_bridge = True
    _INSTALLED = True


install()
