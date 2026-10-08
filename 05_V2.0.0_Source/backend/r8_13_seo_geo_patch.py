"""R8-13/R8-16 SEO/GEO growth HTTP bridge."""
from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from backend import server
from core import seo_geo_autonomy as seo_autonomy
from core import seo_observability
from core import geo_validation
from core.storage import data_root, now_iso, write_json
from core.seo_geo_growth import (
    configure,
    dashboard,
    ensure_baseline,
    generate_staging,
    plan_today,
    reconcile_external_publish_enabled,
    rehydrate_verified_publications,
    record_asset_stage,
    record_geo_observation,
    run_daily_cycle,
    technical_snapshot,
)
from integrations.search_engine_submitter import status as search_submit_status
from integrations import business_data
from integrations import seo_public_deployer
from promotion.search_growth import audit as audit_search_site, status as search_growth_status

_INSTALLED = False
_LAST_GOOD_PAYLOAD = None
_SNAPSHOT_STORE = "r8_13/seo_geo_dashboard_snapshot.json"
_SNAPSHOT_REFRESH_LOCK = threading.Lock()
_SNAPSHOT_REFRESH_PENDING = threading.Event()
_FAST_GET_STATS = {"requests": 0, "errors": 0, "last_ok_at": "", "last_error_at": "", "last_error": ""}


def _save_last_good_payload(payload):
    global _LAST_GOOD_PAYLOAD
    snapshot = deepcopy(payload)
    snapshot["_snapshot_saved_at"] = now_iso()
    _LAST_GOOD_PAYLOAD = snapshot
    try:
        write_json(_SNAPSHOT_STORE, snapshot)
    except OSError:
        pass
    return snapshot


def _load_last_good_payload():
    if isinstance(_LAST_GOOD_PAYLOAD, dict):
        return deepcopy(_LAST_GOOD_PAYLOAD)
    path = data_root() / _SNAPSHOT_STORE
    try:
        if not path.exists():
            return None
        cached = json.loads(path.read_text(encoding="utf-8"))
        return deepcopy(cached) if isinstance(cached, dict) and cached else None
    except (OSError, ValueError):
        return None


def _snapshot_age_seconds(payload):
    raw = str((payload or {}).get("_snapshot_saved_at") or "")
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds())
    except (ValueError, TypeError):
        return None


def _warm_snapshot(lock=None, pending=None):
    # Capture synchronization objects when the work is scheduled. importlib.reload
    # mutates module globals in place, so an old timer must release/clear the
    # exact objects it reserved rather than a replacement from a newer module.
    lock = lock or _SNAPSHOT_REFRESH_LOCK
    pending = pending or _SNAPSHOT_REFRESH_PENDING
    if not lock.acquire(blocking=False):
        pending.clear()
        return
    try:
        _dashboard_payload()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    finally:
        lock.release()
        pending.clear()


def _kick_snapshot_refresh(delay_seconds=1.5):
    lock = _SNAPSHOT_REFRESH_LOCK
    pending = _SNAPSHOT_REFRESH_PENDING
    if lock.locked() or pending.is_set():
        return False
    pending.set()
    timer = threading.Timer(max(0.0, float(delay_seconds)), _warm_snapshot, args=(lock, pending))
    timer.name = "kz-seo-geo-snapshot"
    timer.daemon = True
    timer.start()
    return True


def _overlay_formal_geo_truth(payload):
    """Prefer official A/B truth while preserving legacy local observations.

    R8-13 historically accepted explicit local GEO observations. Existing tests
    and upgraded installs can legitimately contain those rows before the R8-19
    official Evidence ledger has any A/B receipts. Once official Evidence exists
    it becomes authoritative for every owner-facing formal GEO metric.
    """
    result = deepcopy(payload)
    try:
        truth = geo_validation.dashboard()
        official = truth.get("official") or {}
        question_set = truth.get("question_set") or {}
        tested = int(official.get("tested") or 0)
        geo = result.setdefault("geo", {})
        geo["questions"] = int(question_set.get("total") or geo.get("questions") or 50)
        if tested > 0:
            geo.update({
                "tested_questions": tested,
                "observations": tested,
                "mentioned": int(official.get("mentioned") or 0),
                "cited": int(official.get("cited") or 0),
                "recommended": int(official.get("recommended") or 0),
                "mention_rate": official.get("mention_rate"),
                "citation_rate": official.get("citation_rate"),
                "recommendation_rate": official.get("recommendation_rate"),
                "measurement_state": official.get("measurement_state") or "measured",
                "truth_source": "r8-19-official-evidence",
                "evidence_count": int(official.get("evidence_count") or 0),
            })
        else:
            # No formal Evidence yet: do not erase a truthful R8-13 observation.
            legacy_observations = int(geo.get("observations") or 0)
            geo["measurement_state"] = "measured" if legacy_observations > 0 else (
                geo.get("measurement_state") or "not_started"
            )
            geo["truth_source"] = "r8-13-legacy-observation" if legacy_observations > 0 else "r8-19-official-evidence"
            geo["formal_tested_questions"] = 0
            geo["formal_evidence_count"] = 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return result


def _mark_fast_ok(payload):
    _FAST_GET_STATS["requests"] = int(_FAST_GET_STATS.get("requests") or 0) + 1
    _FAST_GET_STATS["last_ok_at"] = now_iso()
    return payload


def _mark_fast_error(error):
    _FAST_GET_STATS["requests"] = int(_FAST_GET_STATS.get("requests") or 0) + 1
    _FAST_GET_STATS["errors"] = int(_FAST_GET_STATS.get("errors") or 0) + 1
    _FAST_GET_STATS["last_error_at"] = now_iso()
    _FAST_GET_STATS["last_error"] = type(error).__name__


def _fast_health_payload():
    cached = _load_last_good_payload()
    age = _snapshot_age_seconds(cached) if cached else None
    return {
        "online": True,
        "service": "seo_geo",
        "snapshot_available": bool(cached),
        "snapshot_saved_at": (cached or {}).get("_snapshot_saved_at") or "",
        "snapshot_age_seconds": round(age, 1) if age is not None else None,
        "refresh_inflight": _SNAPSHOT_REFRESH_LOCK.locked() or _SNAPSHOT_REFRESH_PENDING.is_set(),
        "requests": int(_FAST_GET_STATS.get("requests") or 0),
        "errors": int(_FAST_GET_STATS.get("errors") or 0),
        "last_ok_at": _FAST_GET_STATS.get("last_ok_at") or "",
        "last_error_at": _FAST_GET_STATS.get("last_error_at") or "",
        "last_error": _FAST_GET_STATS.get("last_error") or "",
        "truth": "健康探针不读取主SEO/GEO账本，也不访问外部连接器；只判断本地服务在线与真实快照是否存在。",
    }


def _fast_dashboard_response():
    cached = _load_last_good_payload()
    if cached:
        age = _snapshot_age_seconds(cached)
        _kick_snapshot_refresh(delay_seconds=2.0)
        health = cached.setdefault("service_health", {})
        health["snapshot_saved_at"] = cached.get("_snapshot_saved_at") or ""
        health["snapshot_age_seconds"] = round(age, 1) if age is not None else None
        health["snapshot_mode"] = True
        health["truth"] = "页面优先读取最近一次成功持久化的真实快照，并在后台异步刷新；快照时间单独标注，不把缓存冒充为新的外部回执。"
        return _mark_fast_ok(_overlay_formal_geo_truth(cached))

    # Never make the first page paint wait on optional remote connectors.
    # Return the local ledger immediately, then enrich/persist the full snapshot
    # in a background thread.
    payload = dashboard()
    payload["search_submit"] = _connector_fallback()
    payload["evidence_summary"] = _staging_evidence(payload)
    payload["revenue_os"] = {
        "status": "warming",
        "status_label": "经营数据读取中",
        "connected": False,
        "revenue": None,
        "revenue_status": "verified_revenue_not_connected",
        "attribution_status": "waiting_source_attribution",
        "source_parameter_contract": ["seo", "geo", "search_engine", "ai_citation", "asset_id"],
        "truth": "首屏只读取本地真实账本；RevenueOS与外部连接器将在后台快照刷新完成后显示真实状态。",
    }
    payload["unattended_validation"] = seo_autonomy.validation_status()
    payload["service_health"] = {
        "state": "warming_snapshot",
        "degraded": False,
        "warnings": [],
        "snapshot_mode": True,
        "truth": "正在后台生成完整真实快照；首屏不等待远程连接器。",
    }
    _kick_snapshot_refresh(delay_seconds=2.0)
    return _mark_fast_ok(_overlay_formal_geo_truth(payload))


def _optional_status(label, reader, fallback):
    """Read a non-essential connector without taking the SEO screen offline.

    The desktop dashboard must still be usable when a locally stored account,
    a deployment path, or an optional connector cannot be read during startup.
    A connector's transient failure is shown as its own pending state rather
    than aborting the single dashboard request and making the browser report
    the unhelpful ``Failed to fetch`` message.
    """
    try:
        result = reader()
        return result if isinstance(result, dict) else dict(fallback)
    except Exception as error:  # HTTP boundary: optional status must not break the page.
        result = dict(fallback)
        result["status"] = "unavailable"
        result["reason"] = f"{label}暂时不可用：{type(error).__name__}"
        return result


def _connector_fallback():
    return {
        "connectors": {
            "baidu": {
                "label": "百度搜索资源平台", "channel_group": "search_submission", "setup_state": "API Token/站点授权", "extra_paid_api": False, "configured": False, "ready": False,
                "submit_capable": True, "monitoring_only": False,
                "mode": "普通收录 API", "requires_owner": True,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
            "bing": {
                "label": "Bing / IndexNow", "channel_group": "search_submission", "setup_state": "无需登录，自动初始化", "extra_paid_api": False, "configured": False, "ready": False,
                "submit_capable": True, "monitoring_only": False,
                "mode": "IndexNow", "requires_owner": False,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
            "google": {
                "label": "Google Search Console", "channel_group": "search_submission", "setup_state": "OAuth/站点授权", "extra_paid_api": False, "configured": False, "ready": False,
                "submit_capable": True, "monitoring_only": False,
                "mode": "Search Console Sitemap API", "requires_owner": True,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
            "so360": {
                "label": "360搜索站长平台", "channel_group": "search_submission", "setup_state": "建议配置站点验证与Sitemap", "extra_paid_api": False, "configured": False, "ready": False,
                "submit_capable": False, "monitoring_only": True,
                "mode": "Sitemap / 站长平台", "requires_owner": True,
                "reason": "360站长平台监测状态正在重新读取。",
            },
            "doubao_search": {
                "label": "豆包搜索 / 豆包浏览器", "channel_group": "ai_content_ecosystem", "setup_state": "复用现有豆包API，无需重复配置", "extra_paid_api": False, "configured": True, "ready": False,
                "submit_capable": False, "monitoring_only": True,
                "mode": "GEO/搜索可见性监测", "requires_owner": False,
                "reason": "复用现有豆包能力做可见性监测。",
            },
            "douyin_search": {
                "label": "抖音搜索 / 抖音浏览器", "channel_group": "ai_content_ecosystem", "setup_state": "监测无需额外模型；自动发布时再授权官方账号", "extra_paid_api": False, "configured": False, "ready": False,
                "submit_capable": False, "monitoring_only": True,
                "mode": "搜索/内容生态监测", "requires_owner": False,
                "reason": "抖音搜索监测状态正在重新读取。",
            },
        },
        "ready_engines": [],
        "automation_summary": {"auto_submit_enabled": True, "pending_unique_urls": 0, "submitted_unique_urls": 0, "failed_last_run": 0, "retry_queue": 0},
        "truth": "连接器状态暂不可用；不会影响本地 SEO/GEO 数据和页面查看。",
    }


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 512 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _staging_evidence(payload):
    """Derive owner-facing local evidence without claiming public success."""
    assets = list(payload.get("assets") or [])
    today = datetime.now().astimezone().date().isoformat()
    generated_today = 0
    qc_today = 0
    published_today = 0
    staged_files = 0
    canonical_files = 0
    schema_files = 0
    title_files = 0
    description_files = 0

    for asset in assets:
        if str(asset.get("generated_at") or "").startswith(today):
            generated_today += 1
        if str(asset.get("qc_passed_at") or "").startswith(today):
            qc_today += 1
        if str(asset.get("published_at") or "").startswith(today):
            published_today += 1
        path = Path(str(asset.get("staging_path") or ""))
        if not path.is_file():
            continue
        staged_files += 1
        try:
            html = path.read_text(encoding="utf-8", errors="replace")[:1024 * 1024]
        except OSError:
            continue
        lower = html.lower()
        if "rel=\"canonical\"" in lower or "rel='canonical'" in lower:
            canonical_files += 1
        if "application/ld+json" in lower:
            schema_files += 1
        if "<title>" in lower and "</title>" in lower:
            title_files += 1
        if "name=\"description\"" in lower or "name='description'" in lower:
            description_files += 1

    qc_total = sum(1 for asset in assets if str(asset.get("stage") or "") in {
        "QC_PASSED", "PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"
    })
    return {
        "today_generated": generated_today,
        "today_qc_passed": qc_today,
        "today_published": published_today,
        "asset_total": len(assets),
        "qc_passed_total": qc_total,
        "staged_files": staged_files,
        "canonical_files": canonical_files,
        "schema_files": schema_files,
        "title_files": title_files,
        "description_files": description_files,
        "truth": "本地文件、Title、Description、Canonical、Schema 只代表本地证据；公网状态仍必须由真实URL验证。",
    }


def _revenue_feedback():
    source = _optional_status(
        "RevenueOS经营数据", business_data.business_source_status,
        {"status": "unavailable", "status_label": "暂不可用", "summary": {}, "last_error": "经营数据状态正在重新读取。"},
    )
    summary = source.get("summary") or {}
    funnel = summary.get("funnel") or {}
    orders = summary.get("orders") or {}
    mini = summary.get("mini_program") or {}
    attribution = summary.get("attribution") or {}
    connected = source.get("status") == "connected"
    visits = funnel.get("mini_program_visits")
    if visits is None:
        visits = mini.get("visit_uv")
    consultations = funnel.get("leads")
    if consultations is None:
        consultations = funnel.get("repair_requests")
    return {
        "status": source.get("status") or "not_configured",
        "status_label": source.get("status_label") or ("已连接" if connected else "待接入"),
        "connected": connected,
        "source": source.get("source"),
        "as_of": source.get("remote_as_of") or source.get("last_refresh"),
        "visits": visits,
        "consultations": consultations,
        "orders_today": orders.get("today"),
        "orders_completed": orders.get("completed"),
        "revenue": None,
        "revenue_status": "verified_revenue_not_connected",
        "attribution_status": attribution.get("status") or "waiting_source_attribution",
        "mapped_consultations": attribution.get("mapped_consultations"),
        "mapped_orders": attribution.get("mapped_orders"),
        "asset_id_coverage": attribution.get("asset_id_coverage"),
        "attribution_channels": attribution.get("channels") or {},
        "source_parameter_contract": ["seo", "geo", "search_engine", "ai_citation", "asset_id"],
        "message": source.get("message") or source.get("last_error") or "",
        "truth": "RevenueOS只显示已验证聚合经营数据；来源归因只有服务器明确携带 SEO/GEO/搜索引擎/AI引用/asset_id 证据时才计入。当前没有安全收入聚合字段时显示待接入，不用订单数推算收入。",
    }


def _dashboard_payload():
    global _LAST_GOOD_PAYLOAD
    warnings = []
    deploy = _optional_status(
        "公网部署状态", seo_public_deployer.status,
        {"configured": False, "enabled": False, "ready": False,
         "reason": "公网部署状态正在重新读取。"},
    )
    # GET /api/r8-13/seo-geo is deliberately read-only. Publication receipt
    # rehydration and publish-policy reconciliation run in the autonomous
    # worker, so a browser refresh cannot compete with workers for the Windows
    # truth ledger and make the dashboard disappear.
    payload = dashboard()
    technical = payload.setdefault("technical", {})
    technical["public_site"] = _optional_status(
        "官网探测状态", search_growth_status,
        {"status": "unavailable", "latest_audit": None, "packs": []},
    )
    technical["public_deploy"] = deploy
    search = _optional_status("搜索连接器状态", search_submit_status, _connector_fallback())
    technical["connectors"] = search.get("connectors") or {}
    technical["observability"] = _optional_status(
        "技术审计状态", seo_observability.status,
        {"state": "unavailable", "checked_at": "", "network": {}, "links": {},
         "truth": "技术审计状态正在重新读取。"},
    )
    payload["search_submit"] = search
    payload["evidence_summary"] = _staging_evidence(payload)
    payload["revenue_os"] = _revenue_feedback()
    payload["unattended_validation"] = seo_autonomy.validation_status()
    payload = _overlay_formal_geo_truth(payload)
    geo = payload.setdefault("geo", {})
    geo["measurement_state"] = "measured" if int(geo.get("observations") or 0) > 0 else "not_started"
    payload["service_health"] = {
        "state": "degraded" if warnings else "healthy",
        "degraded": bool(warnings),
        "warnings": warnings,
        "truth": "核心SEO账本可读时页面保持可用；可选连接器或回执同步失败只降级对应子模块，不把整个SEO/GEO工作区判为离线。",
    }
    _save_last_good_payload(payload)
    return payload


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    ensure_baseline()
    # Do not build a full connector snapshot while the HTTP server and browser
    # are still starting. The first SEO/GEO read returns local/last-good truth
    # immediately and schedules enrichment after the response path is usable.
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-13/seo-geo/health":
                handler._json_ok(_fast_health_payload())
                return
            if path == "/api/r8-13/seo-geo":
                handler._json_ok(_fast_dashboard_response())
                return
            if path == "/api/r8-13/seo-geo/technical":
                result = technical_snapshot()
                result["public_site"] = search_growth_status()
                result["public_deploy"] = seo_public_deployer.status()
                result["connectors"] = (search_submit_status().get("connectors") or {})
                handler._json_ok(result)
                return
        except Exception as error:  # Never close the local HTTP connection without JSON.
            if path == "/api/r8-13/seo-geo":
                _mark_fast_error(error)
                fallback = _load_last_good_payload()
                if fallback:
                    saved_at = fallback.get("_snapshot_saved_at") or ""
                    fallback["service_health"] = {
                        "state": "degraded_snapshot",
                        "degraded": True,
                        "warnings": [f"实时刷新延后：{type(error).__name__}"],
                        "snapshot_saved_at": saved_at,
                        "truth": "当前展示最近一次成功持久化的真实快照；系统会自动重试。快照时间单独标注，不把旧快照冒充为新的实时回执。",
                    }
                    handler._json_ok(fallback)
                    return
            handler._json_error(503, f"SEO/GEO 状态暂时不可用：{type(error).__name__}")
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed = {
            "/api/r8-13/seo-geo/config",
            "/api/r8-13/seo-geo/plan",
            "/api/r8-13/seo-geo/generate",
            "/api/r8-13/seo-geo/run",
            "/api/r8-13/seo-geo/audit-site",
            "/api/r8-13/seo-geo/technical-audit",
            "/api/r8-13/seo-geo/asset-stage",
            "/api/r8-13/seo-geo/geo-observation",
        }
        if path not in allowed:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            if path == "/api/r8-13/seo-geo/config":
                handler._json_ok({"config": configure(payload), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/plan":
                handler._json_ok({"result": plan_today(payload.get("limit")), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/generate":
                handler._json_ok({"result": generate_staging(payload.get("limit") or 6), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/run":
                # This action is the owner-facing entry point for the complete
                # SEO loop.  Calling only run_daily_cycle generated local
                # files and left public deployment / IndexNow submission idle;
                # the autonomy controller applies the same truth gates while
                # advancing every ready external stage.
                handler._json_ok({"result": seo_autonomy.run_once(force=bool(payload.get("force"))), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/audit-site":
                site = str(payload.get("site") or dashboard().get("config", {}).get("site_base_url") or "").strip()
                result = audit_search_site({"site": site})
                handler._json_ok({"audit": result, "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/technical-audit":
                result = seo_observability.run(_dashboard_payload())
                handler._json_ok({"audit": result, "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/asset-stage":
                asset_id = str(payload.get("asset_id") or "").strip()
                stage = str(payload.get("stage") or "").strip()
                if not asset_id or not stage:
                    raise ValueError("asset_id 和 stage 不能为空")
                evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
                handler._json_ok({"asset": record_asset_stage(asset_id, stage, evidence), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/geo-observation":
                handler._json_ok({"observation": record_geo_observation(payload), "dashboard": _dashboard_payload()})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_13_seo_geo = True
    _INSTALLED = True


install()
