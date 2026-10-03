"""R8-23.2 Pilot integration: truth APIs, control lease and model routing.

Adds one consistent owner-facing runtime contract without removing legacy APIs.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from core import r8_23_2_runtime_truth as runtime_truth

_INSTALLED = False


def _install_control_lease():
    """A verified Command is necessary but its current Decision Pack must also be valid."""
    from core import command_execution

    original = command_execution.job_is_authorized
    if getattr(original, "_r8232_wrapped", False):
        return

    def job_is_authorized(job):
        if not original(job):
            return False
        pack = runtime_truth.decision_pack()
        if not pack.get("valid"):
            return False
        return str(job.get("command_id") or "") == str(pack.get("command_id") or "")

    job_is_authorized._r8232_wrapped = True
    command_execution.job_is_authorized = job_is_authorized


def _install_model_execution_policy():
    """Make local-first + SEO/GEO Doubao-required policy affect real R7 work."""
    from core import autonomy

    original = autonomy.execute_autonomous
    if getattr(original, "_r8232_wrapped", False):
        return

    def execute_autonomous(job):
        result = original(job)
        task_type = str(job.get("task_type") or "").lower()
        if task_type not in {"seo", "geo", "market", "content", "video", "review"}:
            return result
        mapping = {
            "seo": "seo_semantic_qc",
            "geo": "geo_gap_analysis",
            "market": "general",
            "content": "general",
            "video": "general",
            "review": "general",
        }
        task_kind = mapping.get(task_type, "general")
        prompt = (
            f"任务：{job.get('title') or ''}\n"
            f"任务类型：{task_type}\n"
            "下面是本地确定性执行层已经得到的真实结果摘要，请进行允许范围内的分析/增强/QC。"
            "不得把模型输出描述成真实搜索、正式GEO Evidence、平台发布、咨询或订单。\n"
            + json.dumps(result if isinstance(result, dict) else {"result": result}, ensure_ascii=False, default=str)[:10000]
        )
        try:
            from integrations import model_policy_router
            routed = model_policy_router.execute(task_kind, prompt)
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            routed = {
                "task_kind": task_kind,
                "success": False,
                "degraded": True,
                "error": str(error)[:500],
                "formal_evidence": False,
                "truth_level": "C_auxiliary",
            }
        if not isinstance(result, dict):
            result = {"summary": str(result)}
        result["model_assistance"] = routed
        if routed.get("required_cloud_missing"):
            result["quality_gate"] = "degraded_waiting_doubao_required_step"
            result["publish_eligible"] = False
        else:
            result["quality_gate"] = "passed_or_not_required" if routed.get("success") else "local_execution_only"
            result["publish_eligible"] = task_type not in {"seo", "geo"} or bool(routed.get("success"))
        result["model_truth_rule"] = "模型输出仅为C级辅助；正式外部结果必须由真实Receipt/Evidence证明。"
        return result

    execute_autonomous._r8232_wrapped = True
    autonomy.execute_autonomous = execute_autonomous


def _install_growth_os_policy():
    """Expose the agreed model division on the eight-employee operating view."""
    try:
        from core import r8_23_growth_operating_system as growth_os
    except ImportError:
        return
    original = growth_os.work_packages
    if getattr(original, "_r8232_wrapped", False):
        return

    def work_packages(mission=None, plan=None):
        rows = original(mission, plan)
        for row in rows:
            if not isinstance(row, dict):
                continue
            owner = str(row.get("employee_id") or "")
            if owner == "seo_geo_growth":
                row["model_policy"] = {
                    "local_model": "preferred_first_pass",
                    "doubao_cloud": "required_for_critical_semantic_steps",
                    "chatgpt": "strategy_priority_review",
                }
            else:
                row["model_policy"] = {
                    "local_model": "preferred_high_frequency",
                    "doubao_cloud": "quality_escalation_or_fallback",
                    "chatgpt": "strategy_only",
                }
        return rows

    work_packages._r8232_wrapped = True
    growth_os.work_packages = work_packages


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    _install_control_lease()
    _install_model_execution_policy()
    _install_growth_os_policy()

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path in {"/api/r8-23-2/pilot", "/api/r8-23-2/runtime-truth"}:
                handler._json_ok(runtime_truth.snapshot())
                return
            if path == "/api/version":
                handler._json_ok(runtime_truth.release_manifest())
                return
            if path == "/api/readiness":
                handler._json_ok(runtime_truth.readiness())
                return
            if path == "/api/health":
                ready = runtime_truth.readiness()
                handler._json_ok({
                    "alive": True,
                    "status": "ok" if ready.get("state") != "BLOCKED" else "blocked",
                    "phase": runtime_truth.PILOT_VERSION,
                    "readiness": ready.get("state"),
                    "generated_at": runtime_truth.now_iso(),
                })
                return
            if path in {"/api/runtime-health", "/api/r8-23-2/runtime-health"}:
                snap = runtime_truth.snapshot()
                handler._json_ok({
                    "alive": True,
                    "readiness": snap.get("readiness"),
                    "truth": snap.get("truth"),
                    "queue": snap.get("queue"),
                    "release": snap.get("release"),
                    "generated_at": runtime_truth.now_iso(),
                })
                return
            if path == "/api/r8-23-2/queue":
                handler._json_ok(runtime_truth.queue_diagnostics())
                return
            if path == "/api/r8-23-2/decision-pack":
                handler._json_ok(runtime_truth.decision_pack())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-23-2/model-route":
                length = int(handler.headers.get("Content-Length", "0") or 0)
                if length < 0 or length > 32 * 1024:
                    raise ValueError("请求内容过大")
                body = json.loads(handler.rfile.read(length) or b"{}") if length else {}
                kind = body.get("task_kind") or "general"
                quality = body.get("local_quality")
                handler._json_ok(runtime_truth.model_route(kind, local_quality=quality))
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    _INSTALLED = True


install()
