"""R8-14 SEO/GEO autonomy controller.

This layer turns the R8-13 truthful SEO/GEO ledger into a durable autonomous
work loop without relaxing evidence gates.  It controls what the system may do
without the owner and what must pause for authorization, risk review or a real
external receipt.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from core.storage import now_iso, read_json, write_json
from core.seo_geo_growth import dashboard, ensure_baseline, record_asset_stage, run_daily_cycle

STORE = "r8_14/seo_geo_autonomy.json"
SCHEMA = "kz.seo-geo-autonomy.v1"
MODES = {"observe", "assisted", "autonomous"}

DEFAULT = {
    "schema": SCHEMA,
    "mode": "autonomous",
    "enabled": True,
    "updated_at": "",
    "policy": {
        "auto_discovery": True,
        "auto_plan": True,
        "auto_generate": True,
        "auto_local_qc": True,
        "auto_publish_when_connector_ready": True,
        "auto_submit_when_connector_ready": True,
        "auto_index_monitor": True,
        "auto_geo_monitor": True,
        "auto_attribution": True,
        "owner_required_for_platform_verification": True,
        "owner_required_for_risk_prompt": True,
        "never_fake_publication": True,
        "never_fake_indexing": True,
        "never_fake_geo_visibility": True,
    },
    "last_run_at": "",
    "last_result": {},
    "human_items": [],
    "audit": [],
}


def _load():
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    data.setdefault("mode", "autonomous")
    data.setdefault("enabled", True)
    data.setdefault("policy", deepcopy(DEFAULT["policy"]))
    data.setdefault("human_items", [])
    data.setdefault("audit", [])
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["human_items"] = list(data.get("human_items") or [])[:100]
    data["audit"] = list(data.get("audit") or [])[:500]
    write_json(STORE, data)
    return data


def configure(payload):
    data = _load()
    if "enabled" in payload:
        data["enabled"] = bool(payload.get("enabled"))
    if "mode" in payload:
        mode = str(payload.get("mode") or "").strip().lower()
        if mode not in MODES:
            raise ValueError("mode 必须是 observe / assisted / autonomous")
        data["mode"] = mode
    data["audit"].insert(0, {"at": now_iso(), "kind": "autonomy_config", "mode": data["mode"], "enabled": data["enabled"]})
    _save(data)
    return status()


def _add_human_item(data, key, title, reason, action):
    existing = next((x for x in data["human_items"] if x.get("key") == key and x.get("status") == "open"), None)
    if existing:
        existing["reason"] = reason
        existing["action"] = action
        existing["updated_at"] = now_iso()
        return
    data["human_items"].insert(0, {
        "key": key,
        "status": "open",
        "title": title,
        "reason": reason,
        "action": action,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })


def _close_human_item(data, key):
    for item in data["human_items"]:
        if item.get("key") == key and item.get("status") == "open":
            item["status"] = "resolved"
            item["resolved_at"] = now_iso()


def _local_qc_generated_assets(limit=20):
    snap = dashboard()
    passed = []
    failed = []
    for asset in snap.get("assets", []):
        if len(passed) + len(failed) >= int(limit):
            break
        if asset.get("stage") != "GENERATED":
            continue
        reasons = []
        if not asset.get("title"):
            reasons.append("缺少title")
        if not asset.get("description"):
            reasons.append("缺少description")
        canonical = str(asset.get("canonical") or "")
        if not canonical.startswith(("http://", "https://")):
            reasons.append("canonical无效")
        if not asset.get("staging_path"):
            reasons.append("缺少staging_path")
        if reasons:
            failed.append({"asset_id": asset.get("id"), "reasons": reasons})
            continue
        record_asset_stage(asset.get("id"), "QC_PASSED", {"local_qc": "R8-14 deterministic SEO page QC", "checked_at": now_iso()})
        passed.append(asset.get("id"))
    return {"passed": passed, "failed": failed}


def _external_readiness(snapshot):
    tech = snapshot.get("technical") or {}
    connectors = tech.get("connectors") or {}
    public_site = tech.get("public_site") or {}
    configured_search = [name for name, row in connectors.items() if isinstance(row, dict) and row.get("configured")]
    public_reachable = bool(public_site.get("reachable") or public_site.get("ok") or public_site.get("status") in {"ok", "healthy"})
    return {
        "configured_search_connectors": configured_search,
        "public_site_reachable": public_reachable,
        "publish_connector_ready": False,
        "publish_connector_reason": "R8-14 公网部署连接器尚未绑定；本地生成/QC可自治，公网发布不得伪造。",
    }


def run_once(force=False):
    data = _load()
    if not data.get("enabled"):
        result = {"skipped": True, "reason": "autonomy_disabled"}
        data["last_result"] = result
        data["last_run_at"] = now_iso()
        _save(data)
        return result

    mode = data.get("mode") or "autonomous"
    ensure_baseline()
    local = {"skipped": True, "reason": "observe_mode"}
    qc = {"passed": [], "failed": []}

    if mode in {"assisted", "autonomous"}:
        local = run_daily_cycle(force=bool(force))
        if data["policy"].get("auto_local_qc", True):
            qc = _local_qc_generated_assets(limit=20)

    snap = dashboard()
    readiness = _external_readiness(snap)

    # The absence of a deployment connector is a configuration task, not a fake failure.
    if mode == "autonomous" and data["policy"].get("auto_publish_when_connector_ready", True):
        if readiness["publish_connector_ready"]:
            _close_human_item(data, "seo_public_deploy_connector")
        else:
            _add_human_item(
                data,
                "seo_public_deploy_connector",
                "配置SEO公网部署连接器",
                readiness["publish_connector_reason"],
                "绑定 kazuizhi.com 的真实部署目标后，系统才能把 QC_PASSED 页面自动发布并记录真实公网URL。",
            )

    configured = readiness["configured_search_connectors"]
    if mode == "autonomous" and data["policy"].get("auto_submit_when_connector_ready", True):
        if configured:
            _close_human_item(data, "seo_search_connector")
        else:
            _add_human_item(
                data,
                "seo_search_connector",
                "授权至少一个搜索站长平台",
                "百度/Bing/Google 当前没有可用真实授权，系统不会伪造提交回执。",
                "在统一账号资产中心使用“+ 新增账号”完成官方登录/站点验证。",
            )

    summary = snap.get("summary") or {}
    result = {
        "skipped": False,
        "mode": mode,
        "local_cycle": local,
        "local_qc": qc,
        "external_readiness": readiness,
        "counts": {
            "public_pages": summary.get("public_pages", 0),
            "submitted_urls": summary.get("submitted_urls", 0),
            "indexed_urls": summary.get("indexed_urls", 0),
        },
        "truth": "自治模式只自动执行已具备真实权限和回执能力的步骤；缺少授权/部署连接器时暂停在待我处理，不伪造成功。",
    }
    data["last_run_at"] = now_iso()
    data["last_result"] = result
    data["audit"].insert(0, {"at": now_iso(), "kind": "autonomy_run", "mode": mode, "qc_passed": len(qc["passed"]), "qc_failed": len(qc["failed"])})
    _save(data)
    return result


def status():
    data = _load()
    snap = dashboard()
    open_items = [x for x in data.get("human_items", []) if x.get("status") == "open"]
    return {
        "enabled": bool(data.get("enabled")),
        "mode": data.get("mode") or "autonomous",
        "policy": deepcopy(data.get("policy") or {}),
        "last_run_at": data.get("last_run_at") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
        "human_items": deepcopy(open_items),
        "human_item_count": len(open_items),
        "today": {
            "opportunities": (snap.get("summary") or {}).get("today_opportunities", 0),
            "public_pages": (snap.get("summary") or {}).get("public_pages", 0),
            "submitted_urls": (snap.get("summary") or {}).get("submitted_urls", 0),
            "indexed_urls": (snap.get("summary") or {}).get("indexed_urls", 0),
        },
        "mode_labels": {
            "observe": "观察模式：只分析和监控，不自动生成/发布",
            "assisted": "半自动模式：自动规划、生成、QC，公网发布需老板确认/连接器",
            "autonomous": "自治模式：满足真实权限和安全门槛的步骤自动执行；授权/风控/缺连接器才找老板",
        },
    }
