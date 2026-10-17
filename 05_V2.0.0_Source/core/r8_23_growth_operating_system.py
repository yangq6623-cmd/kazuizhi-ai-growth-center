"""R8-23 final 7x24 autonomous growth operating system.

This layer keeps R8-22 Command -> Mission -> Plan -> Task -> Receipt intact and
adds the permanent operating doctrine agreed with the owner:
- ChatGPT is the only strategic controller.
- Eight AI employees own concrete work packages.
- Local model / RTX 3060 / Doubao / connectors are tools, never competing brains.
- Repair services and personal tasks remain separate business growth engines.
- A capability is routed only when its trigger is present; configured != used.
- External success always requires real Receipt/Evidence.
- Funds are permanently human-only; risky external actions remain graded gates.
"""
from __future__ import annotations

import shutil
import subprocess
from copy import deepcopy

from core.storage import now_iso, read_json, write_json

STATE_FILE = "ops/r8_23_growth_os.json"
UTILIZATION_LIMIT = 500

AI_EMPLOYEES = (
    {"id": "market_intelligence", "name": "市场情报员", "responsibility": "发现真实需求、趋势、竞品和本地机会", "default_capabilities": ["local_model", "doubao_cloud", "search_signals"]},
    {"id": "seo_geo_growth", "name": "SEO/GEO 增长员", "responsibility": "搜索增长、GEO缺口、页面优化与真实复测", "default_capabilities": ["local_model", "doubao_cloud", "seo_website", "search_submission", "formal_geo_browser"]},
    {"id": "content_operations", "name": "内容运营员", "responsibility": "事实型内容、FAQ、落地页和内容质量闭环", "default_capabilities": ["local_model", "doubao_cloud", "seo_website"]},
    {"id": "social_operations", "name": "社媒运营员", "responsibility": "已授权社媒渠道的内容准备、分发和回执跟踪", "default_capabilities": ["local_model", "doubao_cloud", "social_distribution"]},
    {"id": "video_operations", "name": "短视频运营员", "responsibility": "短视频脚本、素材、辅助镜头和本地视频生产", "default_capabilities": ["local_model", "rtx3060", "doubao_cloud", "social_distribution"]},
    {"id": "local_growth", "name": "本地增长员", "responsibility": "区域机会、服务供给、本地渠道与增长动作", "default_capabilities": ["local_model", "maps_local", "mini_program"]},
    {"id": "conversion", "name": "用户转化员", "responsibility": "访问到小程序、咨询、任务和订单的转化分析", "default_capabilities": ["business_data", "mini_program", "local_model"]},
    {"id": "data_review", "name": "数据复盘员", "responsibility": "Receipt/Evidence核验、复盘和下一轮建议", "default_capabilities": ["business_data", "local_model", "doubao_cloud", "chatgpt_controller"]},
)

BUSINESS_ENGINES = (
    {"id": "repair_services", "name": "本地维修增长", "outcomes": ["site_visit", "mini_program_visit", "consultation", "task", "order"]},
    {"id": "personal_tasks", "name": "个人任务增长", "outcomes": ["site_visit", "mini_program_visit", "consultation", "task", "order"]},
)

CAPABILITIES = {
    "chatgpt_controller": {"name": "ChatGPT 总控制大脑", "owners": ["data_review"], "trigger": "经营目标、真实状态变化、周期复盘、异常恢复", "fallback": "异步控制总线/最后有效Mission", "returns_to": "Command/Mission/Controller Plan", "truth_level": "controller", "autonomy": "strategic_controller"},
    "local_model": {"name": "本地大模型", "owners": [x["id"] for x in AI_EMPLOYEES], "trigger": "高频低风险分类、摘要、草稿、预检、批处理", "fallback": "doubao_cloud", "returns_to": "Task result / QC / draft", "truth_level": "C_auxiliary", "autonomy": "automatic_low_risk"},
    "rtx3060": {"name": "RTX 3060 本地算力", "owners": ["video_operations", "content_operations"], "trigger": "本地图片、辅助镜头、视频、GPU推理任务", "fallback": "CPU/云端模型/延后重任务", "returns_to": "素材/视频任务Receipt", "truth_level": "local_execution", "autonomy": "automatic_low_risk"},
    "doubao_cloud": {"name": "豆包云端大模型", "owners": ["market_intelligence", "seo_geo_growth", "content_operations", "social_operations", "video_operations", "data_review"], "trigger": "本地模型不足、复杂生成、云端增强或QC", "fallback": "local_model", "returns_to": "Task result / QC / draft", "truth_level": "C_auxiliary", "autonomy": "automatic_non_financial"},
    "seo_website": {"name": "官网 SEO/GEO 发布", "owners": ["seo_geo_growth", "content_operations"], "trigger": "QC通过且属于已授权官网内容", "fallback": "保留待发布任务", "returns_to": "Public URL + HTTP/Canonical/Schema/robots Receipt", "truth_level": "external_receipt_required", "autonomy": "authorized_owned_media"},
    "search_submission": {"name": "百度 / Bing / Google 搜索提交", "owners": ["seo_geo_growth"], "trigger": "存在新的真实公网URL或实质更新版本", "fallback": "按连接器分别延后，不阻断其他搜索引擎", "returns_to": "Search submission Receipt", "truth_level": "SUBMITTED_only", "autonomy": "authorized_connector"},
    "formal_geo_browser": {"name": "真实外部 AI 网页 A/B 验证", "owners": ["seo_geo_growth", "data_review"], "trigger": "GEO基线、Phase3复测或周期正式验收", "fallback": "记录待验证；普通API/本地模型不得替代", "returns_to": "Formal A/B Evidence", "truth_level": "formal_A_B_evidence", "autonomy": "truth_gated"},
    "remote_agent": {"name": "公网服务器 Remote Agent", "owners": ["seo_geo_growth", "content_operations"], "trigger": "需要服务器侧发布、验证或远程执行", "fallback": "本地安全队列", "returns_to": "Remote execution Receipt", "truth_level": "external_receipt_required", "autonomy": "authorized_server"},
    "social_distribution": {"name": "社媒/内容分发", "owners": ["social_operations", "video_operations"], "trigger": "平台+账号+动作已达到对应L1-L4授权且内容通过QC", "fallback": "defer_channel_and_continue_core_mission", "returns_to": "Post ID / URL / platform Receipt", "truth_level": "external_receipt_required", "autonomy": "graded_L1_L4"},
    "mini_program": {"name": "微信小程序转化承接", "owners": ["local_growth", "conversion"], "trigger": "内容/搜索/社媒产生可归因访问或业务回流", "fallback": "只读经营数据等待恢复", "returns_to": "visit/consultation/task/order evidence", "truth_level": "business_evidence", "autonomy": "read_only_attribution"},
    "business_data": {"name": "经营数据回流", "owners": ["conversion", "data_review"], "trigger": "咨询、任务、订单或周期复盘", "fallback": "最后已验证快照", "returns_to": "Controller review", "truth_level": "verified_business_data", "autonomy": "read_only"},
    "search_signals": {"name": "公开搜索/市场信号", "owners": ["market_intelligence"], "trigger": "周期扫描或需求变化", "fallback": "最近真实公开信号", "returns_to": "Opportunity/Growth signal", "truth_level": "research_signal", "autonomy": "automatic_read_only"},
    "maps_local": {"name": "地图/本地信息信号", "owners": ["local_growth"], "trigger": "区域需求、供给或本地资料需要复核", "fallback": "公开本地数据等待恢复", "returns_to": "Local growth signal", "truth_level": "research_signal", "autonomy": "automatic_read_only"},
}

EMPLOYEE_BY_NAME = {row["name"]: row for row in AI_EMPLOYEES}
EMPLOYEE_BY_ID = {row["id"]: row for row in AI_EMPLOYEES}
TASK_TYPE_OWNER = {
    "market": "market_intelligence", "seo": "seo_geo_growth", "geo": "seo_geo_growth",
    "content": "content_operations", "social": "social_operations", "video": "video_operations",
    "local": "local_growth", "conversion": "conversion", "review": "data_review",
}


def _default_state():
    return {"schema": "kazuizhi.r8_23.growth_os.v1", "utilization": {}, "cycles": [], "updated_at": now_iso()}


def _load():
    data = read_json(STATE_FILE, _default_state())
    if not isinstance(data, dict):
        data = _default_state()
    data.setdefault("utilization", {})
    data.setdefault("cycles", [])
    return data


def _save(data):
    data["schema"] = "kazuizhi.r8_23.growth_os.v1"
    data["updated_at"] = now_iso()
    data["cycles"] = (data.get("cycles") or [])[-200:]
    write_json(STATE_FILE, data)
    return data


def _receipt_id(result):
    if not isinstance(result, dict):
        return None
    for key in ("receipt_id", "receipt", "control_receipt_id"):
        if result.get(key):
            return str(result.get(key))
    submitted = result.get("submitted")
    if isinstance(submitted, list) and submitted:
        first = submitted[0] if isinstance(submitted[0], dict) else {}
        if first.get("receipt"):
            return str(first.get("receipt"))
    return None


def record_utilization(capability_id, *, success=None, result=None, reason="", context=None):
    if capability_id not in CAPABILITIES:
        return None
    data = _load()
    row = data["utilization"].setdefault(capability_id, {"invoke_count": 0, "success_count": 0, "failure_count": 0})
    row["invoke_count"] = int(row.get("invoke_count") or 0) + 1
    if success is True:
        row["success_count"] = int(row.get("success_count") or 0) + 1
    elif success is False:
        row["failure_count"] = int(row.get("failure_count") or 0) + 1
    row.update({
        "last_invoked_at": now_iso(), "last_success": success,
        "last_receipt_id": _receipt_id(result), "last_reason": str(reason or "")[:300],
        "last_context": deepcopy(context or {}),
    })
    if isinstance(result, dict):
        row["last_result_summary"] = {
            key: deepcopy(result.get(key)) for key in ("skipped", "reason", "processed", "submitted_count", "failed_count", "published_count") if key in result
        }
    _save(data)
    return deepcopy(row)


def gpu_status():
    binary = shutil.which("nvidia-smi")
    if not binary:
        return {"detected": False, "ready": False, "reason": "nvidia-smi_not_found"}
    try:
        completed = subprocess.run(
            [binary, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        ready = completed.returncode == 0 and bool(names)
        return {"detected": ready, "ready": ready, "gpus": names[:4], "rtx3060": any("3060" in x for x in names)}
    except (OSError, subprocess.SubprocessError):
        return {"detected": False, "ready": False, "reason": "gpu_probe_failed"}


def _connector_rows():
    try:
        from integrations import seo_geo_connector_router_v2 as router
        matrix = router.snapshot(check_live=False)
        return {str(row.get("id")): row for row in matrix.get("connectors", []) if isinstance(row, dict)}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def capability_status():
    rows = _connector_rows()
    status = {}
    mapping = {
        "seo_website": "seo_public_deployer", "formal_geo_browser": "geo_external_ai_browser",
        "remote_agent": "remote_agent", "mini_program": "mini_program",
    }
    for cap_id, spec in CAPABILITIES.items():
        item = deepcopy(spec)
        item["id"] = cap_id
        item["ready"] = None
        item["state"] = "policy_ready"
        connector = rows.get(mapping.get(cap_id, ""))
        if connector:
            item["ready"] = bool(connector.get("software_route_ready"))
            item["state"] = connector.get("route_state") or "unknown"
            item["external_verified"] = bool(connector.get("external_verified"))
        status[cap_id] = item

    # Search submission is a bundle; one ready engine is enough to be usable.
    search_ids = ("baidu_search_resource_api", "bing_indexnow", "google_search_console")
    search_rows = [rows.get(x) for x in search_ids if rows.get(x)]
    status["search_submission"]["ready"] = any(bool(x.get("software_route_ready")) for x in search_rows)
    status["search_submission"]["state"] = "ready" if status["search_submission"]["ready"] else "waiting_connector"

    # Social is deliberately graded: configured routes do not grant blanket publish authority.
    social_ids = ("douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo")
    social_rows = [rows.get(x) for x in social_ids if rows.get(x)]
    status["social_distribution"]["ready"] = any(bool(x.get("software_route_ready")) for x in social_rows)
    status["social_distribution"]["state"] = "graded_authorization" if social_rows else "not_configured"

    # Model routes expose the real active model without promoting model output to evidence.
    try:
        from integrations.ai_gateway import gateway_status
        gateway = gateway_status()
        local = (gateway.get("routes") or {}).get("local") or {}
        cloud = (gateway.get("routes") or {}).get("cloud") or {}
        status["local_model"].update(ready=bool(local.get("verified")), state=local.get("status") or "unknown", model=local.get("model"), provider=local.get("provider"))
        status["doubao_cloud"].update(ready=bool(cloud.get("verified")), state=cloud.get("status") or "unknown", model=cloud.get("model"), provider=cloud.get("provider"), configured_label=cloud.get("label"))
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    gpu = gpu_status()
    status["rtx3060"].update(ready=bool(gpu.get("ready") and gpu.get("rtx3060")), state="ready" if gpu.get("ready") and gpu.get("rtx3060") else "not_detected", gpu=gpu)

    utilization = _load().get("utilization") or {}
    for cap_id, item in status.items():
        item["utilization"] = deepcopy(utilization.get(cap_id) or {"invoke_count": 0})
    return list(status.values())


def _business_engines_for_objective(objective):
    text = str(objective or "").lower()
    personal_markers = ("个人任务", "社区任务", "宝妈", "邻里", "人人都能赚钱")
    repair_markers = ("维修", "师傅", "水电", "家电", "漏水", "安装", "卡嘴子")
    personal = any(x in text for x in personal_markers)
    repair = any(x in text for x in repair_markers)
    if personal and not repair:
        return ["personal_tasks"]
    if repair and not personal and any(x in text for x in ("维修", "师傅", "水电", "家电", "漏水", "安装")):
        return ["repair_services"]
    return ["repair_services", "personal_tasks"]


def _employee_trigger(employee_id):
    return {
        "market_intelligence": "周期扫描/新市场信号/新问题",
        "seo_geo_growth": "新关键词/排名变化/GEO Gap/复测到期",
        "content_operations": "内容缺口/SEO-GEO计划需要内容",
        "social_operations": "内容已QC且目标平台达到对应授权级别",
        "video_operations": "高价值主题需要视频/素材且GPU能力可用",
        "local_growth": "区域需求/供给/开放范围变化",
        "conversion": "新增访问/咨询/任务/订单",
        "data_review": "Receipt/Evidence变化/周期复盘/异常",
    }.get(employee_id, "Controller Plan触发")


def work_packages(mission=None, plan=None):
    mission = mission or {}
    plan = plan or {}
    objective = str(mission.get("command_objective") or mission.get("goal") or plan.get("objective") or "")
    engines = _business_engines_for_objective(objective)
    packages = []
    for employee in AI_EMPLOYEES:
        packages.append({
            "package_id": f"{plan.get('plan_id') or 'PLAN'}:{employee['id']}",
            "employee_id": employee["id"], "employee_owner": employee["name"],
            "responsibility": employee["responsibility"],
            "business_engines": engines,
            "trigger": _employee_trigger(employee["id"]),
            "capability_candidates": list(employee["default_capabilities"]),
            "expected_return": "Task Receipt/Evidence -> ChatGPT Controller review",
            "status": "eligible_when_triggered",
        })
    return packages


def _employee_for_job(job):
    name = str(job.get("agent") or "")
    if name in EMPLOYEE_BY_NAME:
        return EMPLOYEE_BY_NAME[name]
    owner_id = TASK_TYPE_OWNER.get(str(job.get("task_type") or "").lower(), "data_review")
    return EMPLOYEE_BY_ID[owner_id]


def annotate_current_jobs(mission=None):
    try:
        from core import r7_engine
    except ImportError:
        return {"annotated": 0}
    mission = mission or {}
    command_id = str(mission.get("command_id") or "")
    mission_id = str(mission.get("mission_id") or "")
    if not command_id and not mission_id:
        return {"annotated": 0}
    changed = 0
    with r7_engine.LOCK:
        data = r7_engine._store()
        for job in data.get("items", []):
            if not isinstance(job, dict) or job.get("state") not in {"queued", "running"}:
                continue
            if command_id and str(job.get("command_id") or "") != command_id and mission_id and str(job.get("mission_id") or "") != mission_id:
                continue
            employee = _employee_for_job(job)
            title = str(job.get("title") or "")
            engine = "personal_tasks" if "个人任务" in title or "社区任务" in title else "repair_services"
            updates = {
                "employee_owner_id": employee["id"], "employee_owner": employee["name"],
                "business_engine": job.get("business_engine") or engine,
                "capability_candidates": list(employee["default_capabilities"]),
                "evidence_return": "Receipt/Evidence -> Controller",
            }
            if any(job.get(k) != v for k, v in updates.items()):
                job.update(updates, updated_at=now_iso())
                changed += 1
        if changed:
            write_json(r7_engine.JOBS, data)
    return {"annotated": changed, "command_id": command_id, "mission_id": mission_id}


def decision_cycle(mission=None, plan=None, reason="controller_tick"):
    mission = mission or {}
    plan = plan or {}
    annotation = annotate_current_jobs(mission)
    packages = work_packages(mission, plan)
    state = _load()
    cycle = {
        "at": now_iso(), "reason": reason,
        "command_id": mission.get("command_id"), "mission_id": mission.get("mission_id"),
        "plan_id": plan.get("plan_id"), "work_packages": len(packages),
        "jobs_annotated": annotation.get("annotated", 0),
        "business_engines": _business_engines_for_objective(mission.get("command_objective") or mission.get("goal") or ""),
    }
    state.setdefault("cycles", []).append(cycle)
    _save(state)
    return {"cycle": cycle, "work_packages": packages, "annotation": annotation}


def snapshot(mission=None, plan=None):
    if mission is None or plan is None:
        try:
            from core import r8_22_autonomous_convergence as convergence
            state = convergence._load_state()
            from core import autonomous_ops
            ops = autonomous_ops._load()
            mission = mission or autonomous_ops._find_mission(ops, mission_id=state.get("active_mission_id")) or {}
            plan = plan or state.get("plan") or {}
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
            mission = mission or {}
            plan = plan or {}
    state = _load()
    return {
        "schema": "kazuizhi.r8_23.growth_os.v1",
        "generated_at": now_iso(),
        "controller": {"id": "chatgpt_controller", "name": "ChatGPT 总控制大脑", "exclusive_strategy_authority": True},
        "business_engines": deepcopy(BUSINESS_ENGINES),
        "employees": deepcopy(AI_EMPLOYEES),
        "work_packages": work_packages(mission, plan),
        "capabilities": capability_status(),
        "recent_cycles": (state.get("cycles") or [])[-10:][::-1],
        "mission_id": mission.get("mission_id"), "command_id": mission.get("command_id"), "plan_id": plan.get("plan_id"),
        "outcome_scope": ["site_visit", "mini_program_visit", "consultation", "task", "order"],
        "forbidden_outcome_scope": ["money", "amount", "revenue", "profit", "roi"],
        "external_authorization": "平台+账号+动作按L1→L4逐级授权；连接存在不等于自动发布权限。",
        "truth_rule": "本地模型/豆包/RTX3060是执行工具，不是正式外部Evidence；所有公网发布、搜索提交、正式GEO和经营结果只认真实Receipt/Evidence。",
        "operating_rule": "能力按触发条件调用，不为展示而强制调用；单一能力失败时局部降级，核心Mission继续。",
    }
