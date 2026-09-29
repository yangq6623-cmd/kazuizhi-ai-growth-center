"""Truthful production monitor and five-shot review controls for the owner UI.

This layer does not invent progress. It only reports real local AI activity,
GPU telemetry when nvidia-smi is available, persisted production tasks, shots,
and real candidate outputs already recorded by the content center.
"""
from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from backend import server as _server
from backend import ai_gateway_patch as _ai
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
_ORIGINAL_IMPORT = _center.import_director_plan


def _iso_now():
    return datetime.now(timezone.utc).isoformat()


def _set_runtime(**patch):
    with _RUNTIME_LOCK:
        _RUNTIME.update(patch)


def _tracked_proxy(payload):
    _set_runtime(
        status="running",
        stage="本地文本 AI",
        message="正在使用本地模型理解内容、改写或生成导演方案。",
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


def _merge_fifth_shot(shots):
    """Normalize owner simple-mode production to exactly five shots.

    If a director returns six or more shots, preserve the first four and merge
    the remaining result/CTA material into the fifth shot. Every shot requests
    two or three candidates; the default is three.
    """
    cleaned = [dict(item) for item in shots if isinstance(item, dict)]
    if len(cleaned) < 5:
        return cleaned
    if len(cleaned) == 5:
        result = cleaned
    else:
        tail = cleaned[4:]
        fifth = dict(tail[0])
        narration = [str(x.get("narration") or x.get("dialogue") or "").strip() for x in tail]
        narration = [x for x in narration if x]
        fifth["purpose"] = "结果证明与品牌收尾"
        fifth["narration"] = " ".join(narration)[:500]
        try:
            fifth["duration_seconds"] = min(12, max(1, sum(float(x.get("duration_seconds") or 0) for x in tail)))
        except (TypeError, ValueError):
            fifth["duration_seconds"] = 6
        locks = []
        negatives = []
        for item in tail:
            for value in item.get("consistency_locks") or []:
                if value not in locks:
                    locks.append(value)
            for value in item.get("negative_constraints") or []:
                if value not in negatives:
                    negatives.append(value)
        fifth["consistency_locks"] = locks[:8]
        fifth["negative_constraints"] = negatives[:10]
        result = cleaned[:4] + [fifth]
    for item in result:
        try:
            count = int(item.get("candidate_count") or 3)
        except (TypeError, ValueError):
            count = 3
        item["candidate_count"] = max(2, min(count, 3))
    return result


def _five_shot_import(payload):
    data = dict(payload or {})
    shots = data.get("shots")
    if isinstance(shots, list):
        normalized = _merge_fifth_shot(shots)
        if len(normalized) != 5:
            raise ValueError("简单模式需要恰好 5 个镜头，请先让 AI 导演补足 5 个镜头")
        data["shots"] = normalized
    return _ORIGINAL_IMPORT(data)


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
        return {
            "project": None,
            "shots": [],
            "tasks": [],
            "outputs": [],
            "confirmed_shots": 0,
            "total_shots": 0,
        }
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
        "tasks": tasks[:30],
        "outputs": outputs,
        "confirmed_shots": len([x for x in shots if x.get("id") in selected_shot_ids]),
        "total_shots": len(shots),
    }


def _monitor_payload():
    with _RUNTIME_LOCK:
        runtime = dict(_RUNTIME)
    runtime["elapsed_seconds"] = _elapsed_seconds(runtime.get("started_at")) if runtime.get("status") == "running" else 0
    runtime["loaded_models"] = _ai._loaded_ollama_models()
    return {
        "ok": True,
        "mode": "quality_first",
        "text_ai": runtime,
        "gpu": _gpu_snapshot(),
        "production": _current_project_snapshot(),
        "policy": {
            "shot_count": 5,
            "candidates_per_shot": "2-3",
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
    task = {
        "id": _center._id("TASK"),
        "project_id": project["id"],
        "shot_id": shot_id,
        "kind": "镜头候选修改/重做",
        "executor": "本地 Router（按显存串行）",
        "status": "待本地执行器",
        "progress": 0,
        "created_at": _center.now_iso(),
        "detail": f"老板修改要求：{instruction}",
        "owner_instruction": instruction,
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
    if len(shots) != 5:
        raise ValueError("必须先确认 5 个镜头")
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
        "detail": "5 个镜头均已确认，等待串行合成完整视频。",
    }
    data["tasks"].insert(0, task)
    project["status"] = "等待完整成片合成"
    _center._audit(data, "final_render_queued", project_id, task["detail"])
    _center._save(data)
    return task


_ai._proxy_local_chat = _tracked_proxy
_center.import_director_plan = _five_shot_import

if not getattr(_server.DashboardHandler, "_kz_production_monitor_patched", False):
    _get = _server.DashboardHandler.do_GET
    _post = _server.DashboardHandler.do_POST

    def _do_get(self):
        if urlsplit(self.path).path == "/api/production-monitor":
            self._json_ok(_monitor_payload())
            return
        return _get(self)

    def _do_post(self):
        path = urlsplit(self.path).path
        if path not in {
            "/api/ai-content-center/candidates/select",
            "/api/ai-content-center/candidates/revise",
            "/api/ai-content-center/final/queue",
        }:
            return _post(self)
        origin = self.headers.get("Origin")
        if origin and origin not in {
            f"http://127.0.0.1:{self.server.server_port}",
            f"http://localhost:{self.server.server_port}",
        }:
            self._json_error(403, "仅允许本机工作台操作")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 64 * 1024:
            self._json_error(400, "请求内容不正确")
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path.endswith("/select"):
                result = _select_candidate(payload)
            elif path.endswith("/revise"):
                result = _queue_revision(payload)
            else:
                result = _queue_final_render(payload)
            self._json_ok(result, code=201)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json_error(400, error)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_production_monitor_patched = True
