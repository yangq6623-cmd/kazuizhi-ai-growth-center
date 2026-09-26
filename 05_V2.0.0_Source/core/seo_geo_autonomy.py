"""R8-14/R8-17 SEO/GEO autonomy controller.

Local discovery, planning, generation and deterministic QC can run autonomously.
R8-15 allows guarded public deployment only when a real deployment connector is
ready. R8-16 adds real search submission: a page only reaches SUBMITTED after an
external search endpoint returns an observable acceptance receipt. R8-17 routes
public deployment through the desktop Remote Agent when that connector is ready.
"""
from __future__ import annotations

from copy import deepcopy

from core.storage import now_iso, read_json, write_json
from core.seo_geo_growth import dashboard, ensure_baseline, record_asset_stage, run_daily_cycle
from integrations import search_engine_submitter
from integrations import seo_public_deployer

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
        "auto_technical_audit": True,
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
        existing["title"] = title
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
        record_asset_stage(asset.get("id"), "QC_PASSED", {"local_qc": "R8 deterministic SEO page QC", "checked_at": now_iso()})
        passed.append(asset.get("id"))
    return {"passed": passed, "failed": failed}


def _external_readiness(snapshot):
    public_site = (snapshot.get("technical") or {}).get("public_site") or {}
    public_reachable = bool(public_site.get("reachable") or public_site.get("ok") or public_site.get("status") in {"ok", "healthy"})
    # Resolve through the integration modules at call time. R8-17 patches these
    # module attributes during startup; importing function objects by value would
    # leave this autonomy controller stuck on the old R8-15 local-IIS connector.
    deploy = seo_public_deployer.status()
    search = search_engine_submitter.status()
    connectors = search.get("connectors") or {}
    configured_search = [name for name, row in connectors.items() if isinstance(row, dict) and row.get("configured")]
    ready_search = [name for name, row in connectors.items() if isinstance(row, dict) and row.get("ready")]
    return {
        "configured_search_connectors": configured_search,
        "ready_search_connectors": ready_search,
        "public_site_reachable": public_reachable,
        "publish_connector_ready": bool(deploy.get("ready")),
        "publish_connector_reason": deploy.get("reason") or "",
        "publish_connector": deploy,
        "search_submitter": search,
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
    public_deploy = {"skipped": True, "reason": "mode_or_policy_gate"}
    search_submit = {"skipped": True, "reason": "mode_or_policy_gate"}
    # Public technical audits run in the background scheduler, never in this
    # synchronous startup/action path. A slow external page must not delay the
    # desktop dashboard from opening.
    technical_audit = {"scheduled": bool(data["policy"].get("auto_technical_audit", True))}

    if mode in {"assisted", "autonomous"}:
        local = run_daily_cycle(force=bool(force))
        if data["policy"].get("auto_local_qc", True):
            qc = _local_qc_generated_assets(limit=20)

    snap = dashboard()
    readiness = _external_readiness(snap)
    if mode == "autonomous" and data["policy"].get("auto_publish_when_connector_ready", True):
        if readiness["publish_connector_ready"]:
            _close_human_item(data, "seo_public_deploy_connector")
            public_deploy = seo_public_deployer.deploy_pending(limit=20)
            failures = list(public_deploy.get("failed") or [])
            if failures:
                _add_human_item(
                    data,
                    "seo_public_deploy_verification",
                    "SEO公网发布验证未全部通过",
                    f"本轮有 {len(failures)} 个页面未通过公网HTTP/内容验证，系统没有把它们标记为已发布。",
                    "检查 IIS /seo/ 映射、HTTPS公网访问和页面内容；验证通过后系统会自动续跑。",
                )
            else:
                _close_human_item(data, "seo_public_deploy_verification")
        else:
            _add_human_item(
                data,
                "seo_public_deploy_connector",
                "配置SEO公网部署连接器",
                readiness["publish_connector_reason"] or "公网部署连接器尚未就绪。",
                "只需配置真实网站目录；连接器仅写 <site_root>/seo/，不会碰 Web.config、App_Data、uploads、数据库或现有业务目录。",
            )

    # Refresh after deployment so search submission only sees pages that have real
    # public verification receipts. A ready public connector is enough to attempt
    # R8-16 because IndexNow can mint/host its own key inside managed /seo/.
    snap = dashboard()
    readiness = _external_readiness(snap)
    if mode == "autonomous" and data["policy"].get("auto_submit_when_connector_ready", True):
        if readiness["publish_connector_ready"] or readiness["ready_search_connectors"]:
            # Initialize IndexNow as soon as verified public deployment is
            # available.  This persists a real key-file verification result;
            # it does not claim a search-engine receipt by itself.
            if readiness["publish_connector_ready"]:
                search_engine_submitter.initialize_indexnow()
            search_submit = search_engine_submitter.submit_pending(limit=20)
            refreshed_search = search_engine_submitter.status()
            if refreshed_search.get("ready_engines"):
                _close_human_item(data, "seo_search_connector")
            else:
                _add_human_item(
                    data,
                    "seo_search_connector",
                    "等待公网部署或搜索连接器就绪",
                    "当前没有可用的真实搜索提交连接器；系统不会伪造提交回执。IndexNow 不需要账号授权。",
                    "优先完成公网部署后由系统自动启用 IndexNow；百度/GSC 仅在需要各自平台能力时，再通过官方入口完成站点 token/OAuth 授权。",
                )
            submit_failures = list(search_submit.get("failed") or [])
            if submit_failures:
                _add_human_item(
                    data,
                    "seo_search_submission_error",
                    "搜索平台提交未全部通过",
                    f"本轮有 {len(submit_failures)} 个搜索提交动作没有取得成功接收回执。",
                    "查看搜索连接器状态与回执；修复授权、站点验证或公网key文件后系统会自动重试。",
                )
            else:
                _close_human_item(data, "seo_search_submission_error")
        else:
            _add_human_item(
                data,
                "seo_search_connector",
                "等待SEO公网部署配置",
                "当前缺少真实公网部署条件，因此 IndexNow 不能安全初始化；系统不会伪造提交回执。",
                "先完成SEO公网部署；系统会自动建立并验证 IndexNow key。百度和Google仅在需要其平台功能时，才通过官方入口完成真实授权。",
            )

    # Final refresh: owner-facing counts must use the exact same truth ledger after
    # both public deployment and external submission.
    snap = dashboard()
    readiness = _external_readiness(snap)
    summary = snap.get("summary") or {}
    result = {
        "skipped": False,
        "mode": mode,
        "local_cycle": local,
        "local_qc": qc,
        "public_deploy": public_deploy,
        "search_submit": search_submit,
        "technical_audit": technical_audit,
        "external_readiness": readiness,
        "counts": {
            "public_pages": summary.get("public_pages", 0),
            "submitted_urls": summary.get("submitted_urls", 0),
            "indexed_urls": summary.get("indexed_urls", 0),
        },
        "truth": "自治模式只执行具备真实权限和回执能力的步骤；PUBLISHED 必须有公网验证，SUBMITTED 必须有搜索平台接收回执，抓取/收录/排名仍需后续外部证据。",
    }
    data["last_run_at"] = now_iso()
    data["last_result"] = result
    data["audit"].insert(0, {
        "at": now_iso(),
        "kind": "autonomy_run",
        "mode": mode,
        "qc_passed": len(qc["passed"]),
        "qc_failed": len(qc["failed"]),
        "published": len(public_deploy.get("published") or []),
        "submitted": int(search_submit.get("submitted_count") or 0),
    })
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
        "public_deploy": seo_public_deployer.status(),
        "search_submit": search_engine_submitter.status(),
        "today": {
            "opportunities": (snap.get("summary") or {}).get("today_opportunities", 0),
            "public_pages": (snap.get("summary") or {}).get("public_pages", 0),
            "submitted_urls": (snap.get("summary") or {}).get("submitted_urls", 0),
            "indexed_urls": (snap.get("summary") or {}).get("indexed_urls", 0),
        },
        "mode_labels": {
            "observe": "观察模式：只分析和监控，不自动生成/发布",
            "assisted": "半自动模式：自动规划、生成、QC，公网发布需老板确认/连接器",
            "autonomous": "自治模式：连接器就绪后自动部署、验证并提交搜索平台；授权/风控/缺连接器才找老板",
        },
    }
