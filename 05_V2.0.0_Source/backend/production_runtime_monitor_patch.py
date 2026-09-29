"""Truthful dynamic production monitor and shot-review controls.

This layer never invents progress. It reports real local AI activity, real GPU
telemetry when nvidia-smi is available, persisted production tasks, dynamic
storyboards, and candidate outputs already recorded by the content center.
"""
from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from backend import server as _server
from backend import ai_gateway_patch as _ai
from backend import dynamic_director_policy_patch as _policy
from promotion import ai_production_center as _center

_RUNTIME_LOCK = threading.Lock()
_RUNTIME = {
    "status": "idle",
    "stage": "等待任务",
    "message": "当前没有本地 AI 文本任务。",
    "started_at": "",
    "finished_at": "",
    "last_error": "",
}
_ORIGINAL_PROXY = _ai._proxy_local_chat


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _set_runtime(**patch):
    with _RUNTIME_LOCK:
        _RUNTIME.update(patch)


def _tracked_proxy(payload):
    _set_runtime(
        status="running",
        stage="本地文本 AI",
        message="正在使用本地模型理解内容、原创改写或生成导演方案。",
        started_at=_iso_now(),
        finished_at="",
        last_error="",
    )
    try:
        result = _ORIGINAL_PROXY(payload)
        _set_runtime(
            status="completed",
            stage="本地文本 AI",
            message="本地文本 AI 已完成，本轮显存正在释放。",
            finished_at=_iso_now(),
            last_error="",
        )
        return result
    except Exception as error:
        _set_runtime(
            status="error",
            stage="本地文本 AI",
            message="本地 AI 本轮未完成，系统保留已有进度。",
            finished_at=_iso_now(),
            last_error=str(error),
        )
        raise


def _importance(raw, index, total):
    value = str(raw.get("importance") or "").strip().upper()
    if value in {"S", "A", "B"}:
        return value
    text = " ".join(str(raw.get(k) or "") for k in ("purpose", "action", "narration"))
    if index == 1 or any(key in text for key in ("钩子", "前三秒", "关键", "核心", "正脸")):
        return "S"
    if index == total or any(key in text for key in ("结果", "CTA", "品牌", "专业判断", "演示")):
        return "A"
    return "B"


def _candidate_budget(importance, quality):
    matrix = {
        "fast": {"S": 2, "A": 1, "B": 1},
        "standard": {"S": 2, "A": 2, "B": 1},
        "high": {"S": 3, "A": 2, "B": 1},
        "premium": {"S": 3, "A": 3, "B": 2},
    }
    return matrix.get(quality, matrix["high"]).get(importance, 1)


def _dynamic_import(payload):
    """Import a director plan with dynamic shot and candidate counts.

    The creative decision is made by the director. This function only enforces
    safety limits, persists continuity locks and normalizes a suspicious
    all-three-candidates default into a quality-aware budget.
    """
    data = _center._load()
    raw_shots = payload.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("导演方案至少需要一个镜头")
    policy = _policy.load_policy()
    max_shots = int(policy.get("max_shots") or 40)
    if len(raw_shots) > max_shots:
        raise ValueError(f"当前安全上限为 {max_shots} 个镜头，请让 AI 导演合并重复镜头")

    reference_id = _center._clean(payload.get("reference_id"), "参考内容ID", 80, False)
    creative_id = _center._clean(payload.get("creative_id"), "创意ID", 80, False)
    director_plan_id = _center._clean(payload.get("director_plan_id") or _center._id("DIR"), "导演方案ID", 80)
    project = {
        "id": _center._id("AIP"), "created_at": _center.now_iso(),
        "name": _center._clean(payload.get("name"), "项目名称", 100),
        "script": _center._clean(payload.get("script"), "文案", 6000, False),
        "ratio": _center._clean(payload.get("ratio") or "9:16", "画幅", 10),
        "status": "动态分镜已确认", "default_character_id": "", "default_scene_id": "",
        "default_voice_id": "", "owner_note": _center._clean(payload.get("owner_note"), "项目说明", 500, False),
        "reference_id": reference_id, "creative_id": creative_id,
        "director_plan_id": director_plan_id,
        "director_goal": _center._clean(payload.get("director_goal"), "视频目标", 80, False),
        "director_style": _center._clean(payload.get("director_style"), "全片风格", 80, False),
        "director_summary": _center._clean(payload.get("director_summary"), "导演摘要", 1200, False),
        "production_mode": policy["mode"],
        "quality_profile": policy["quality"],
    }
    data["projects"].insert(0, project)

    explicit_counts = []
    for raw in raw_shots:
        try:
            explicit_counts.append(int(raw.get("candidate_count")))
        except (TypeError, ValueError, AttributeError):
            explicit_counts.append(0)
    all_default_three = bool(explicit_counts) and all(value == 3 for value in explicit_counts)

    shots = []
    total_duration = 0.0
    total = len(raw_shots)
    for index, raw in enumerate(raw_shots, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"镜头{index}格式不正确")
        try:
            duration = float(raw.get("duration_seconds") or 4)
        except (TypeError, ValueError):
            duration = 4.0
        duration = max(1.0, min(duration, 12.0))
        importance = _importance(raw, index, total)
        try:
            requested_count = int(raw.get("candidate_count") or 0)
        except (TypeError, ValueError):
            requested_count = 0
        if requested_count not in {1, 2, 3} or all_default_three:
            candidate_count = _candidate_budget(importance, policy["quality"])
        else:
            candidate_count = requested_count

        shot = {
            "id": _center._id("SHOT"), "project_id": project["id"], "order": index,
            "purpose": _center._clean(raw.get("purpose") or f"镜头 {index}", "镜头目的", 160),
            "narration": _center._clean(raw.get("narration"), "台词/旁白", 500, False),
            "duration_seconds": duration,
            "shot_type": _center._clean(raw.get("shot_type") or "中景", "景别", 60),
            "motion": _center._clean(raw.get("motion") or "稳定", "运镜", 80),
            "candidate_count": candidate_count,
            "importance": importance,
            "status": "待候选生成", "source": "GPT 动态导演确认方案",
            "character": _center._clean(raw.get("character"), "人物", 100, False),
            "scene": _center._clean(raw.get("scene"), "场景", 120, False),
            "props": _center._text_list(raw.get("props"), "物品", 8, 80),
            "action": _center._clean(raw.get("action"), "动作", 240, False),
            "generation_method": _center._clean(raw.get("generation_method") or "真实素材优先", "生成方式", 80),
            "consistency_locks": _center._text_list(raw.get("consistency_locks"), "一致性锁", 8, 100),
            "negative_constraints": _center._text_list(raw.get("negative_constraints"), "负面约束", 10, 120),
            "reference_id": reference_id, "creative_id": creative_id,
            "director_plan_id": director_plan_id,
        }
        total_duration += duration
        data["storyboards"].append(shot)
        shots.append(shot)

    if not project["script"]:
        project["script"] = "\n".join(
            f"镜头{shot['order']}：{shot['narration'] or shot['purpose']}" for shot in shots
        )[:6000]

    total_candidates = sum(int(shot.get("candidate_count") or 1) for shot in shots)
    task = {
        "id": _center._id("TASK"), "project_id": project["id"], "kind": "GPT 动态导演分镜导入",
        "executor": "GPT 总控 → 本地内容生产中心", "status": "已完成",
        "progress": 100, "created_at": _center.now_iso(),
        "detail": f"已确认并导入 {len(shots)} 个动态镜头（约 {total_duration:g} 秒），计划 {total_candidates} 个候选；尚未生成候选或成片。",
    }
    data["tasks"].insert(0, task)
    _center._audit(data, "dynamic_director_plan_imported", project["id"], task["detail"])
    _center._save(data)
    return {"project": project, "storyboards": shots, "task": task}


def _gpu_snapshot():
    command = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    kwargs = {"timeout": 3, "text": True, "encoding": "utf-8", "errors": "replace"}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        output = subprocess.check_output(command, **kwargs).strip().splitlines()[0]
        parts = [x.strip() for x in output.split(",")]
        return {
            "available": True,
            "utilization_percent": float(parts[0]),
            "memory_used_mb": float(parts[1]),
            "memory_total_mb": float(parts[2]),
            "temperature_c": float(parts[3]),
        }
    except (OSError, subprocess.SubprocessError, IndexError, ValueError):
        return {"available": False}


def _elapsed_seconds(started_at):
    if not started_at:
        return 0
    try:
        started = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - started.astimezone(timezone.utc)).total_seconds()))
    except (ValueError, TypeError):
        return 0


def _current_project_snapshot():
    data = _center.dashboard()
    project = (data.get("projects") or [None])[0]
    if not project:
        return {"project": None, "shots": [], "tasks": [], "outputs": [], "confirmed_shots": 0, "total_shots": 0, "planned_candidates": 0}
    project_id = project.get("id")
    shots = sorted(
        [x for x in data.get("storyboards") or [] if x.get("project_id") == project_id],
        key=lambda x: x.get("order") or 0,
    )
    tasks = [x for x in data.get("tasks") or [] if x.get("project_id") == project_id]
    outputs = [x for x in data.get("outputs") or [] if x.get("project_id") == project_id]
    selected_shot_ids = {
        x.get("shot_id") for x in outputs
        if x.get("selected") is True or str(x.get("status") or "") in {"已采用", "已确认"}
    }
    return {
        "project": project,
        "shots": shots,
        "tasks": tasks[:60],
        "outputs": outputs,
        "confirmed_shots": len([x for x in shots if x.get("id") in selected_shot_ids]),
        "total_shots": len(shots),
        "planned_candidates": sum(int(x.get("candidate_count") or 1) for x in shots),
    }


def _monitor_payload():
    with _RUNTIME_LOCK:
        runtime = dict(_RUNTIME)
    runtime["elapsed_seconds"] = _elapsed_seconds(runtime.get("started_at")) if runtime.get("status") == "running" else 0
    runtime["loaded_models"] = _ai._loaded_ollama_models()
    return {
        "ok": True,
        "mode": "quality_first_dynamic",
        "text_ai": runtime,
        "gpu": _gpu_snapshot(),
        "production": _current_project_snapshot(),
        "policy": _policy.load_policy() | {
            "shot_count": "dynamic",
            "candidates_per_shot": "1-3",
            "quality_first": True,
            "fake_percent": False,
        },
    }


def _find_output(data, candidate_id, shot_id):
    for item in data.get("outputs") or []:
        if item.get("id") == candidate_id and item.get("shot_id") == shot_id:
            return item
    raise ValueError("没有找到该真实候选文件")


def _select_candidate(payload):
    data = _center._load()
    shot_id = str(payload.get("shot_id") or "").strip()
    candidate_id = str(payload.get("candidate_id") or "").strip()
    if not shot_id or not candidate_id:
        raise ValueError("镜头和候选不能为空")
    shot = _center._find(data["storyboards"], shot_id, "镜头")
    chosen = _find_output(data, candidate_id, shot_id)
    for item in data.get("outputs") or []:
        if item.get("shot_id") == shot_id:
            item["selected"] = item.get("id") == candidate_id
            if item.get("selected"):
                item["status"] = "已采用"
    shot["status"] = "候选已确认"
    chosen["selected_at"] = _iso_now()
    _center._audit(data, "candidate_selected", shot_id, f"老板已采用候选 {candidate_id}。")
    _center._save(data)
    return {"ok": True, "shot": shot, "candidate": chosen}


def _queue_revision(payload):
    data = _center._load()
    shot_id = str(payload.get("shot_id") or "").strip()
    instruction = str(payload.get("instruction") or "重新生成一个不同候选").strip()[:500]
    shot = _center._find(data["storyboards"], shot_id, "镜头")
    project = _center._find(data["projects"], shot["project_id"], "项目")
    locks = "、".join(shot.get("consistency_locks") or []) or "沿用当前人物/场景/风格"
    task = {
        "id": _center._id("TASK"),
        "project_id": project["id"],
        "shot_id": shot_id,
        "kind": "镜头候选修改/重做",
        "executor": "GPT 总控 → 本地模型（按显存串行）",
        "status": "待本地执行器",
        "progress": 0,
        "created_at": _center.now_iso(),
        "detail": f"老板修改要求：{instruction}；连续性锁：{locks}",
        "owner_instruction": instruction,
        "consistency_locks": list(shot.get("consistency_locks") or []),
    }
    data["tasks"].insert(0, task)
    shot["status"] = "候选重做已排队"
    _center._audit(data, "candidate_revision_queued", shot_id, task["detail"])
    _center._save(data)
    return task


def _queue_final_render(payload):
    data = _center._load()
    project_id = str(payload.get("project_id") or "").strip()
    project = _center._find(data["projects"], project_id, "项目")
    shots = sorted([x for x in data["storyboards"] if x.get("project_id") == project_id], key=lambda x: x.get("order") or 0)
    if not shots:
        raise ValueError("当前项目还没有可合成镜头")
    outputs = data.get("outputs") or []
    selected = {x.get("shot_id") for x in outputs if x.get("project_id") == project_id and (x.get("selected") is True or x.get("status") in {"已采用", "已确认"})}
    missing = [str(x.get("order")) for x in shots if x.get("id") not in selected]
    if missing:
        raise ValueError("还有镜头未选择候选：" + "、".join(missing))
    task = {
        "id": _center._id("TASK"),
        "project_id": project_id,
        "kind": "完整成片合成",
        "executor": "配音 / 字幕 / FFmpeg / 质检",
        "status": "待本地执行器",
        "progress": 0,
        "created_at": _center.now_iso(),
        "detail": f"{len(shots)} 个动态镜头均已确认，等待串行合成完整视频。",
    }
    data["tasks"].insert(0, task)
    project["status"] = "等待完整成片合成"
    _center._audit(data, "final_render_queued", project_id, task["detail"])
    _center._save(data)
    return task


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > 64 * 1024:
        raise ValueError("请求内容不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


_ai._proxy_local_chat = _tracked_proxy
_center.import_director_plan = _dynamic_import

if not getattr(_server.DashboardHandler, "_kz_production_monitor_patched", False):
    _get = _server.DashboardHandler.do_GET
    _post = _server.DashboardHandler.do_POST

    def _do_get(self):
        path = urlsplit(self.path).path
        if path == "/api/production-monitor":
            self._json_ok(_monitor_payload())
            return
        if path == "/api/production-policy":
            self._json_ok(_policy.load_policy())
            return
        return _get(self)

    def _do_post(self):
        path = urlsplit(self.path).path
        allowed = {
            "/api/production-policy",
            "/api/ai-content-center/candidates/select",
            "/api/ai-content-center/candidates/revise",
            "/api/ai-content-center/final/queue",
        }
        if path not in allowed:
            return _post(self)
        origin = self.headers.get("Origin")
        if origin and origin not in {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }:
            self._json_error(403, "仅允许本机工作台操作")
            return
        try:
            payload = _read_body(self)
            if path == "/api/production-policy":
                result = _policy.save_policy(payload)
                code = 200
            elif path.endswith("/select"):
                result = _select_candidate(payload)
                code = 201
            elif path.endswith("/revise"):
                result = _queue_revision(payload)
                code = 201
            else:
                result = _queue_final_render(payload)
                code = 201
            self._json_ok(result, code=code)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json_error(400, error)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_production_monitor_patched = True
