"""R8-19 GEO Phase 2 HTTP bridge for truth-gated GEO validation.

Browser validation remains the default no-API path. Phase 2 adds deterministic
Evidence analysis and comparison. It never creates evidence, upgrades C-level
data, or makes strategy decisions; ChatGPT remains the controller.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import geo_analysis
from core import geo_validation as geo_core
from core.geo_validation import (
    DECISION_PATH,
    audit_events,
    bootstrap_question_set,
    claim_next_task,
    create_and_enqueue_plan,
    dashboard,
    decision,
    fail_task,
    manual_requirements,
    pause_task,
    question_set,
    queue_summary,
    receipts,
    record_result,
    resume_task,
    retry_task,
    set_decision,
)
from core.mission_ledger import snapshot as mission_ledger_snapshot
from core.storage import now_iso, write_json
from integrations import geo_browser_validation, geo_local_precheck, geo_openai_search_executor, geo_chatgpt_analyzer

_INSTALLED = False
PHASE1_PROVIDERS = {"browser_external_ai", "openai_web_search"}
DEFAULT_PROVIDER = "browser_external_ai"
DEFAULT_TEST_METHOD = "browser"


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 512 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _task_id(payload):
    value = str((payload or {}).get("task_id") or "").strip()
    if not value:
        raise ValueError("task_id_required")
    return value


def _normalized_providers(value):
    raw = value if isinstance(value, list) else [value] if value else [DEFAULT_PROVIDER]
    providers = []
    for item in raw:
        provider = str(item or "").strip()
        if not provider:
            continue
        if provider not in PHASE1_PROVIDERS:
            raise ValueError(f"unsupported_phase1_geo_provider:{provider}")
        if provider not in providers:
            providers.append(provider)
    return providers or [DEFAULT_PROVIDER]


def _active_mission_context():
    try:
        ledger = mission_ledger_snapshot()
        active = ledger.get("active_mission") if isinstance(ledger, dict) else None
        if not isinstance(active, dict):
            return {}
        mission_id = str(active.get("mission_id") or "").strip()
        if not mission_id:
            return {}
        command = active.get("command") if isinstance(active.get("command"), dict) else {}
        return {
            "mission_id": mission_id,
            "mission_title": str(active.get("title") or "").strip(),
            "mission_goal": str(active.get("goal") or "").strip(),
            "source_command_id": str(command.get("command_id") or "").strip(),
            "source_decision_pack_id": str(command.get("decision_pack_id") or "").strip(),
        }
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, ImportError):
        return {}


def _method_for_provider(provider):
    return "api" if provider == "openai_web_search" else "browser"


def _persist_decision_extras(current, providers=None, mission_context=None):
    value = dict(current or {})
    selected = providers or value.get("test_providers") or [DEFAULT_PROVIDER]
    if providers is None and selected == ["openai_web_search"]:
        try:
            if not geo_openai_search_executor.status().get("ready"):
                selected = [DEFAULT_PROVIDER]
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            selected = [DEFAULT_PROVIDER]
    value["test_providers"] = _normalized_providers(selected)
    value["test_method"] = _method_for_provider(value["test_providers"][0])
    value["provider_selection_controller"] = "chatgpt"
    value["platform_self_polling_allowed"] = False
    value["api_required"] = False
    value["browser_first"] = value["test_providers"][0] == "browser_external_ai"
    if mission_context:
        value["bound_to_current_mission"] = True
        value["source_command_id"] = mission_context.get("source_command_id") or value.get("source_command_id") or ""
        value["source_decision_pack_id"] = mission_context.get("source_decision_pack_id") or value.get("source_decision_pack_id") or ""
    else:
        value.setdefault("bound_to_current_mission", False)
    write_json(DECISION_PATH, value)
    return value


def _effective_decision():
    current = decision()
    mission = _active_mission_context()
    if mission and mission.get("mission_id") != current.get("mission_id"):
        current = set_decision(
            {
                "decision_id": current.get("decision_id"),
                "command_id": current.get("command_id"),
                "mission_id": mission.get("mission_id"),
                "mission_title": mission.get("mission_title") or current.get("mission_title"),
                "today_goal": current.get("today_goal"),
                "judgement": current.get("judgement"),
                "next_decision_condition": current.get("next_decision_condition"),
                "daily_test_limit": current.get("daily_test_limit"),
                "created_at": current.get("created_at"),
            }
        )
    return _persist_decision_extras(current, mission_context=mission)


def _set_controller_decision(payload):
    payload = dict(payload or {})
    providers = _normalized_providers(payload.pop("test_providers", None))
    mission = _active_mission_context()
    if mission:
        payload["mission_id"] = mission.get("mission_id")
        payload["mission_title"] = mission.get("mission_title") or payload.get("mission_title")
    current = set_decision(payload)
    return _persist_decision_extras(current, providers=providers, mission_context=mission)


def _migrate_pending_api_tasks_to_browser():
    queue = geo_core._load_queue()
    changed = 0
    for task in queue.get("tasks") or []:
        if task.get("provider") != "openai_web_search":
            continue
        if task.get("state") not in {"queued", "authorization_required"}:
            continue
        task["provider"] = "browser_external_ai"
        task["test_method"] = "browser"
        task["state"] = "queued"
        task["authorization_reason"] = ""
        task["failure_reason"] = ""
        task["failure_code"] = ""
        task["updated_at"] = now_iso()
        changed += 1
    if changed:
        geo_core._save_queue(queue)
        geo_core._audit("geo_pending_tasks_migrated_to_browser", {"count": changed})
    return changed


def _refresh_analysis():
    return geo_analysis.refresh(receipts(1000))


def _dashboard_with_executor():
    value = dashboard()
    value["decision"] = _effective_decision()
    browser = geo_browser_validation.status()
    api = geo_openai_search_executor.status()
    local = geo_local_precheck.status()
    value["executor"] = browser
    value["browser_executor"] = browser
    value["api_executor"] = api
    value["local_precheck"] = local
    value["analysis"] = geo_analysis.status()
    value["chatgpt_analysis"] = geo_chatgpt_analyzer.status()
    value["execution_modes"] = {
        "default": "browser",
        "browser": {"ready": True, "requires_api": False, "label": "网页真实验证"},
        "api": {"ready": bool(api.get("ready")), "requires_api": True, "label": "API验证（可选）"},
        "local_precheck": {"ready": bool(local.get("ready")), "official_truth": False, "label": "本地预检（C级）"},
    }
    value["manual"] = manual_requirements()
    return value


def _preflight_status():
    value = _dashboard_with_executor()
    return {
        "ready": True,
        "default_mode": "browser",
        "browser": value.get("browser_executor"),
        "api": value.get("api_executor"),
        "local_precheck": value.get("local_precheck"),
        "queue": value.get("queue") or {},
        "analysis": value.get("analysis") or {},
        "recommended_run_size": 1,
        "next_step": "先完成真实外部AI证据，再进入第二阶段自动分析与比较",
        "truth_rule": "API不是必需项；浏览器真实外部AI结果可形成A级Evidence，本地模型固定为C级辅助。",
    }


def _eligible_question_ids(requested=None):
    questions = question_set().get("questions") or []
    known = {item.get("question_id") for item in questions}
    tasks = queue_summary().get("tasks") or []
    active_ids = {
        item.get("question_id")
        for item in tasks
        if item.get("state") in {"queued", "running", "authorization_required", "paused"}
    }
    failed_ids = {item.get("question_id") for item in tasks if item.get("state") == "failed"}
    official_ids = {
        item.get("question_id")
        for item in receipts(1000)
        if item.get("official_truth") and item.get("evidence_level") in {"A", "B"}
    }
    source = list(requested or [item.get("question_id") for item in questions])
    unknown = [qid for qid in source if qid not in known]
    if unknown:
        raise ValueError(f"unknown_geo_question_id:{unknown[0]}")
    failed_requested = [qid for qid in source if qid in failed_ids]
    if requested and failed_requested:
        raise ValueError("failed_question_requires_chatgpt_retry")
    return [qid for qid in source if qid in known and qid not in active_ids and qid not in failed_ids and qid not in official_ids]


def _prepare_browser_task(payload):
    _migrate_pending_api_tasks_to_browser()
    platform = str((payload or {}).get("platform") or "custom_web")
    queue = queue_summary().get("tasks") or []
    formal_50_batch = bool((payload or {}).get("formal_50_batch"))
    current = _effective_decision()
    if formal_50_batch and int(current.get("daily_test_limit") or 10) < 50:
        current = _set_controller_decision({**current, "daily_test_limit": 50})
    if formal_50_batch or not any(item.get("state") == "queued" for item in queue):
        eligible = _eligible_question_ids((payload or {}).get("question_ids") or None)
        create_and_enqueue_plan(
            limit=max(1, min(int((payload or {}).get("limit") or 1), 50, int(current.get("daily_test_limit") or 10))),
            provider="browser_external_ai",
            test_method="browser",
            mission_id=current.get("mission_id", ""),
            question_ids=eligible,
        )
    claim = claim_next_task(
        {
            "real_external": True,
            "authorization_ready": True,
            "provider_ready": True,
            "provider": platform,
            "test_method": "browser",
            "executor_id": geo_browser_validation.EXECUTOR_ID,
        }
    )
    task = claim.get("task") or {}
    return {"claim": claim, "contract": geo_browser_validation.contract(task, platform=platform)}


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/r8-19/geo":
            handler._json_ok(_dashboard_with_executor())
            return
        if path == "/api/r8-19/geo/preflight":
            handler._json_ok(_preflight_status())
            return
        if path == "/api/r8-19/geo/questions":
            handler._json_ok(question_set())
            return
        if path == "/api/r8-19/geo/queue":
            handler._json_ok(queue_summary())
            return
        if path == "/api/r8-19/geo/receipts":
            handler._json_ok({"receipts": receipts(query.get("limit", [200])[0])})
            return
        if path == "/api/r8-19/geo/analysis":
            handler._json_ok(geo_analysis.snapshot())
            return
        if path == "/api/r8-19/geo/analysis/brief":
            handler._json_ok(geo_analysis.analysis_pack())
            return
        if path == "/api/r8-19/geo/analysis/chatgpt":
            handler._json_ok({"status": geo_chatgpt_analyzer.status(), "snapshot": geo_chatgpt_analyzer.snapshot()})
            return
        if path == "/api/r8-19/geo/manual":
            handler._json_ok(manual_requirements())
            return
        if path == "/api/r8-19/geo/audit":
            handler._json_ok({"events": audit_events(query.get("limit", [200])[0])})
            return
        if path == "/api/r8-19/geo/executor":
            handler._json_ok(geo_browser_validation.status())
            return
        if path == "/api/r8-19/geo/api-executor":
            handler._json_ok(geo_openai_search_executor.status())
            return
        if path == "/api/r8-19/geo/local-precheck":
            handler._json_ok({"status": geo_local_precheck.status(), "results": geo_local_precheck.results(query.get("limit", [50])[0])})
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-19/geo/bootstrap",
            "/api/r8-19/geo/plan",
            "/api/r8-19/geo/run",
            "/api/r8-19/geo/receipt",
            "/api/r8-19/geo/fail",
            "/api/r8-19/geo/pause",
            "/api/r8-19/geo/resume",
            "/api/r8-19/geo/retry",
            "/api/r8-19/geo/decision",
            "/api/r8-19/geo/browser/prepare",
            "/api/r8-19/geo/browser/receipt",
            "/api/r8-19/geo/local-precheck/run",
            "/api/r8-19/geo/analysis/refresh",
            "/api/r8-19/geo/analysis/chatgpt/run",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-19/geo/bootstrap":
                result = bootstrap_question_set(force=bool(payload.get("force")))
            elif path == "/api/r8-19/geo/plan":
                current = _effective_decision()
                requested = payload.get("question_ids") or None
                eligible_ids = _eligible_question_ids(requested)
                provider = current.get("test_providers", [DEFAULT_PROVIDER])[0]
                if provider == "openai_web_search" and payload.get("require_executor_ready"):
                    api = geo_openai_search_executor.status()
                    if not api.get("ready"):
                        raise ValueError(f"geo_executor_not_ready:{api.get('reason') or 'external_validation_not_ready'}")
                result = create_and_enqueue_plan(
                    limit=payload.get("limit", current.get("daily_test_limit", 10)),
                    provider=provider,
                    test_method=_method_for_provider(provider),
                    mission_id=current.get("mission_id", ""),
                    question_ids=eligible_ids,
                )
            elif path == "/api/r8-19/geo/browser/prepare":
                result = _prepare_browser_task(payload)
            elif path == "/api/r8-19/geo/browser/receipt":
                result = geo_browser_validation.record_browser_result(payload)
                _refresh_analysis()
            elif path == "/api/r8-19/geo/local-precheck/run":
                result = geo_local_precheck.run(limit=payload.get("limit", 1), question_ids=payload.get("question_ids"))
            elif path == "/api/r8-19/geo/run":
                current = _effective_decision()
                provider = current.get("test_providers", [DEFAULT_PROVIDER])[0]
                mode = str(payload.get("mode") or provider).strip()
                if mode == "external_contract":
                    result = claim_next_task(payload.get("executor") or payload)
                elif mode == "openai_web_search" and provider == "openai_web_search":
                    result = geo_openai_search_executor.run_once()
                    if result.get("ok"):
                        _refresh_analysis()
                else:
                    raise ValueError("geo_executor_not_selected_by_chatgpt_decision")
            elif path == "/api/r8-19/geo/receipt":
                result = record_result(payload)
                _refresh_analysis()
            elif path == "/api/r8-19/geo/analysis/refresh":
                result = _refresh_analysis()
            elif path == "/api/r8-19/geo/analysis/chatgpt/run":
                result = geo_chatgpt_analyzer.run()
            elif path == "/api/r8-19/geo/fail":
                result = fail_task(_task_id(payload), payload.get("reason") or "execution_failed")
            elif path == "/api/r8-19/geo/pause":
                result = pause_task(_task_id(payload))
            elif path == "/api/r8-19/geo/resume":
                result = resume_task(_task_id(payload))
            elif path == "/api/r8-19/geo/retry":
                result = retry_task(_task_id(payload), approved_by=str(payload.get("approved_by") or "chatgpt"))
            else:
                result = _set_controller_decision(payload)
            handler._json_ok({"result": result, "geo": _dashboard_with_executor()})
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_19_geo_validation = True
    _INSTALLED = True


install()
