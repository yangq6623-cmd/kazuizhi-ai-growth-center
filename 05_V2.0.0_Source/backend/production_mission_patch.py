"""Persistent content task cards, shot checkpoints, resume and retry control.

This is the durable production foundation used before the real ComfyUI executor
is attached. It never invents rendered files. A candidate is only marked done
when an executor explicitly reports a checkpoint.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from backend import server as _server
from backend import production_runtime_monitor_patch as _monitor
from core.storage import read_json, write_json
from promotion import ai_production_center as _center

MISSION_FILE = "r8/content_production_missions.json"
SCHEMA_VERSION = 1
DONE_STATES = {"generated", "qc_passed", "selected", "completed"}
RETRY_BACKOFF_SECONDS = (30, 120, 300)


def _now_dt():
    return datetime.now(timezone.utc)


def _now():
    return _now_dt().isoformat()


def _parse_time(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _default_store():
    return {"schema_version": SCHEMA_VERSION, "missions": []}


def _load():
    data = read_json(MISSION_FILE, _default_store())
    if not isinstance(data, dict):
        data = _default_store()
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("missions", [])
    if not isinstance(data["missions"], list):
        data["missions"] = []
    return data


def _save(data):
    data["schema_version"] = SCHEMA_VERSION
    return write_json(MISSION_FILE, data)


def _id(prefix):
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def _mission_for_project(data, project_id):
    for item in data.get("missions") or []:
        if item.get("project_id") == project_id:
            return item
    return None


def _mission_by_id(data, mission_id):
    if mission_id:
        for item in data.get("missions") or []:
            if item.get("id") == mission_id:
                return item
        raise ValueError("没有找到该内容生产任务")
    missions = data.get("missions") or []
    if not missions:
        raise ValueError("当前没有内容生产任务")
    return missions[0]


def _candidate_key(shot_id, index):
    return f"{shot_id}:C{index:02d}"


def _shot_contract(shot):
    count = max(1, min(int(shot.get("candidate_count") or 1), 3))
    candidates = []
    for index in range(1, count + 1):
        candidates.append({
            "key": _candidate_key(shot.get("id"), index),
            "index": index,
            "status": "pending",
            "attempts": 0,
            "max_retries": 3,
            "manual_retries": 0,
            "next_retry_at": "",
            "started_at": "",
            "finished_at": "",
            "last_error": "",
            "output_id": "",
            "file_url": "",
            "updated_at": _now(),
        })
    return {
        "shot_id": shot.get("id"),
        "order": shot.get("order"),
        "purpose": shot.get("purpose") or "",
        "importance": shot.get("importance") or "",
        "candidate_count": count,
        "generation_method": shot.get("generation_method") or "",
        "consistency_locks": list(shot.get("consistency_locks") or []),
        "status": "pending",
        "selected_output_id": "",
        "candidates": candidates,
        "updated_at": _now(),
    }


def _content_card(project, payload):
    reference_id = project.get("reference_id") or ""
    source_kind = "reference" if reference_id else (
        "automatic" if project.get("production_mode") == "auto" else "manual_or_assisted"
    )
    return {
        "source_kind": source_kind,
        "source_title": str(payload.get("source_title") or project.get("name") or "")[:200],
        "source_url": str(payload.get("source_url") or "")[:1200],
        "reference_id": reference_id,
        "creative_id": project.get("creative_id") or "",
        "original_text": str(payload.get("source_text") or payload.get("original_input") or "")[:12000],
        "ai_analysis": str(payload.get("source_analysis_summary") or project.get("director_summary") or "")[:4000],
        "final_script": str(project.get("script") or "")[:12000],
        "director_plan_id": project.get("director_plan_id") or "",
        "review_status": "待生产",
        "publish_status": "未发布",
        "performance": {},
    }


def _create_mission(project, shots, payload=None):
    payload = payload or {}
    mission = {
        "id": _id("PM"),
        "project_id": project.get("id"),
        "name": project.get("name") or "内容生产任务",
        "created_at": _now(),
        "updated_at": _now(),
        "status": "ready",
        "stage": "candidate_generation",
        "production_mode": project.get("production_mode") or "assisted",
        "quality_profile": project.get("quality_profile") or "high",
        "retry_policy": {"max_retries": 3, "backoff_seconds": list(RETRY_BACKOFF_SECONDS)},
        "content_card": _content_card(project, payload),
        "shots": [_shot_contract(shot) for shot in sorted(shots, key=lambda x: x.get("order") or 0)],
        "current": {},
        "events": [{"at": _now(), "kind": "mission_created", "detail": "内容任务卡与镜头检查点已建立；尚未生成视频。"}],
    }
    return mission


def _sync_project(project, shots, payload=None):
    data = _load()
    existing = _mission_for_project(data, project.get("id"))
    if existing:
        return existing
    mission = _create_mission(project, shots, payload)
    data["missions"].insert(0, mission)
    _save(data)
    return mission


def _ensure_latest_mission():
    dashboard = _center.dashboard()
    project = (dashboard.get("projects") or [None])[0]
    if not project:
        return None
    shots = [x for x in dashboard.get("storyboards") or [] if x.get("project_id") == project.get("id")]
    if not shots:
        return None
    return _sync_project(project, shots)


def _recover_interrupted():
    data = _load()
    changed = False
    for mission in data.get("missions") or []:
        if mission.get("status") == "running":
            mission["status"] = "paused"
            mission["updated_at"] = _now()
            mission.setdefault("events", []).insert(0, {
                "at": _now(), "kind": "restart_recovery",
                "detail": "检测到上次任务中断，已保留已完成检查点；可从未完成镜头继续。",
            })
            changed = True
        for shot in mission.get("shots") or []:
            for candidate in shot.get("candidates") or []:
                if candidate.get("status") == "generating":
                    candidate["status"] = "pending"
                    candidate["last_error"] = "应用中断，检查点已保留；本候选等待恢复。"
                    candidate["updated_at"] = _now()
                    changed = True
    if changed:
        _save(data)


def _promote_due_retries(mission):
    now = _now_dt()
    changed = False
    for shot in mission.get("shots") or []:
        for candidate in shot.get("candidates") or []:
            if candidate.get("status") != "retry_wait":
                continue
            due = _parse_time(candidate.get("next_retry_at"))
            if due is None or due <= now:
                candidate["status"] = "pending"
                candidate["next_retry_at"] = ""
                candidate["updated_at"] = _now()
                changed = True
    return changed


def _iter_candidates(mission):
    for shot in sorted(mission.get("shots") or [], key=lambda x: x.get("order") or 0):
        for candidate in shot.get("candidates") or []:
            yield shot, candidate


def _recompute(mission):
    total = 0
    done = 0
    terminal_failed = 0
    waiting_retry = 0
    generating = 0
    selected_shots = 0
    for shot in mission.get("shots") or []:
        if shot.get("selected_output_id"):
            selected_shots += 1
        shot_done = True
        for candidate in shot.get("candidates") or []:
            total += 1
            state = candidate.get("status")
            if state in DONE_STATES:
                done += 1
            else:
                shot_done = False
            if state == "failed_terminal":
                terminal_failed += 1
            elif state == "retry_wait":
                waiting_retry += 1
            elif state == "generating":
                generating += 1
        if shot.get("selected_output_id"):
            shot["status"] = "selected"
        elif shot_done and shot.get("candidates"):
            shot["status"] = "candidates_ready"
        elif generating:
            shot.setdefault("status", "pending")
    if terminal_failed:
        mission["status"] = "needs_attention"
    elif generating:
        mission["status"] = "running"
    elif total and done == total:
        mission["status"] = "awaiting_review"
    elif waiting_retry and mission.get("status") != "paused":
        mission["status"] = "waiting_retry"
    mission["updated_at"] = _now()
    return {
        "total_candidates": total,
        "completed_candidates": done,
        "terminal_failed": terminal_failed,
        "waiting_retry": waiting_retry,
        "generating": generating,
        "selected_shots": selected_shots,
        "total_shots": len(mission.get("shots") or []),
    }


def _summary(mission, include_card=True, include_shots=True):
    stats = _recompute(mission)
    result = {
        "id": mission.get("id"),
        "project_id": mission.get("project_id"),
        "name": mission.get("name"),
        "status": mission.get("status"),
        "stage": mission.get("stage"),
        "production_mode": mission.get("production_mode"),
        "quality_profile": mission.get("quality_profile"),
        "current": mission.get("current") or {},
        "created_at": mission.get("created_at"),
        "updated_at": mission.get("updated_at"),
        **stats,
    }
    if include_card:
        result["content_card"] = mission.get("content_card") or {}
    if include_shots:
        result["shots"] = mission.get("shots") or []
    return result


def current_mission():
    _ensure_latest_mission()
    data = _load()
    if not data.get("missions"):
        return {"ok": True, "mission": None}
    mission = data["missions"][0]
    changed = _promote_due_retries(mission)
    summary = _summary(mission)
    if changed:
        _save(data)
    return {"ok": True, "mission": summary}


def list_missions():
    data = _load()
    return {"ok": True, "missions": [_summary(x, include_card=False, include_shots=False) for x in data.get("missions") or []]}


def resume(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    _promote_due_retries(mission)
    if mission.get("status") not in {"awaiting_review", "completed"}:
        mission["status"] = "running"
    mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "resume", "detail": "继续未完成生产任务。"})
    mission["updated_at"] = _now()
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


def pause(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    if mission.get("status") not in {"completed", "awaiting_review"}:
        mission["status"] = "paused"
    mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "pause", "detail": "任务已暂停；已完成检查点不会重跑。"})
    mission["updated_at"] = _now()
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


def claim_next(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    _promote_due_retries(mission)
    if mission.get("status") == "paused":
        raise ValueError("任务已暂停，请先恢复任务")
    for shot, candidate in _iter_candidates(mission):
        if candidate.get("status") != "pending":
            continue
        candidate["status"] = "generating"
        candidate["attempts"] = int(candidate.get("attempts") or 0) + 1
        candidate["started_at"] = _now()
        candidate["updated_at"] = _now()
        mission["status"] = "running"
        mission["current"] = {
            "shot_id": shot.get("shot_id"), "shot_order": shot.get("order"),
            "candidate_key": candidate.get("key"), "candidate_index": candidate.get("index"),
            "attempt": candidate.get("attempts"),
        }
        mission["updated_at"] = _now()
        _save(data)
        return {
            "ok": True,
            "work": {
                "mission_id": mission.get("id"), "project_id": mission.get("project_id"),
                "shot": shot, "candidate": candidate,
                "quality_profile": mission.get("quality_profile"),
            },
        }
    stats = _recompute(mission)
    if stats["terminal_failed"]:
        mission["status"] = "needs_attention"
    elif stats["waiting_retry"]:
        mission["status"] = "waiting_retry"
    elif stats["total_candidates"] and stats["completed_candidates"] == stats["total_candidates"]:
        mission["status"] = "awaiting_review"
    else:
        mission["status"] = "ready"
    mission["current"] = {}
    _save(data)
    return {"ok": True, "work": None, "mission": _summary(mission)}


def _find_candidate(mission, key):
    for shot, candidate in _iter_candidates(mission):
        if candidate.get("key") == key:
            return shot, candidate
    raise ValueError("没有找到该镜头候选检查点")


def checkpoint(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    shot, candidate = _find_candidate(mission, str(payload.get("candidate_key") or "").strip())
    state = str(payload.get("status") or "generated").strip()
    if state not in DONE_STATES:
        raise ValueError("检查点状态不正确")
    candidate["status"] = state
    candidate["finished_at"] = _now()
    candidate["updated_at"] = _now()
    candidate["next_retry_at"] = ""
    candidate["last_error"] = ""
    if payload.get("output_id"):
        candidate["output_id"] = str(payload.get("output_id"))[:160]
    if payload.get("file_url"):
        candidate["file_url"] = str(payload.get("file_url"))[:2000]
    if state == "selected":
        shot["selected_output_id"] = candidate.get("output_id") or candidate.get("key")
        shot["status"] = "selected"
    mission["current"] = {}
    mission.setdefault("events", []).insert(0, {
        "at": _now(), "kind": "checkpoint",
        "detail": f"镜头{shot.get('order')} 候选{candidate.get('index')} 已保存检查点：{state}。",
    })
    _recompute(mission)
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


def fail(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    shot, candidate = _find_candidate(mission, str(payload.get("candidate_key") or "").strip())
    error = str(payload.get("error") or "本轮执行失败").strip()[:1000]
    attempts = int(candidate.get("attempts") or 0)
    max_retries = int(candidate.get("max_retries") or 3)
    retryable = payload.get("retryable") is not False
    if retryable and attempts < max_retries:
        delay = RETRY_BACKOFF_SECONDS[min(max(attempts - 1, 0), len(RETRY_BACKOFF_SECONDS) - 1)]
        candidate["status"] = "retry_wait"
        candidate["next_retry_at"] = (_now_dt() + timedelta(seconds=delay)).isoformat()
        detail = f"镜头{shot.get('order')} 候选{candidate.get('index')} 第{attempts}次未完成，{delay}秒后可自动重试。"
    else:
        candidate["status"] = "failed_terminal"
        candidate["next_retry_at"] = ""
        detail = f"镜头{shot.get('order')} 候选{candidate.get('index')} 已达到自动重试上限，需要人工确认后再试。"
    candidate["last_error"] = error
    candidate["updated_at"] = _now()
    mission["current"] = {}
    mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "candidate_failed", "detail": detail})
    _recompute(mission)
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


def retry_failed(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    key = str(payload.get("candidate_key") or "").strip()
    changed = 0
    for _, candidate in _iter_candidates(mission):
        if candidate.get("status") != "failed_terminal":
            continue
        if key and candidate.get("key") != key:
            continue
        attempts = int(candidate.get("attempts") or 0)
        candidate["max_retries"] = max(int(candidate.get("max_retries") or 3), attempts + 3)
        candidate["manual_retries"] = int(candidate.get("manual_retries") or 0) + 1
        candidate["status"] = "pending"
        candidate["next_retry_at"] = ""
        candidate["updated_at"] = _now()
        changed += 1
    if not changed:
        raise ValueError("没有需要人工重试的失败候选")
    mission["status"] = "running"
    mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "manual_retry", "detail": f"已重新开放 {changed} 个失败候选。"})
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


def update_card(payload):
    data = _load()
    mission = _mission_by_id(data, str(payload.get("mission_id") or "").strip())
    card = mission.setdefault("content_card", {})
    limits = {
        "source_title": 200, "source_url": 1200, "original_text": 12000,
        "ai_analysis": 4000, "final_script": 12000,
        "review_status": 80, "publish_status": 80,
    }
    for key, limit in limits.items():
        if key in payload:
            card[key] = str(payload.get(key) or "")[:limit]
    mission["updated_at"] = _now()
    _save(data)
    return {"ok": True, "mission": _summary(mission)}


_ORIGINAL_IMPORT = _center.import_director_plan


def _mission_import(payload):
    result = _ORIGINAL_IMPORT(payload)
    project = result.get("project") or {}
    shots = result.get("storyboards") or []
    mission = _sync_project(project, shots, payload)
    result["mission"] = _summary(mission)
    return result


# Keep the mission record synchronized with the owner's existing review actions.
_ORIGINAL_SELECT = _monitor._select_candidate
_ORIGINAL_REVISE = _monitor._queue_revision
_ORIGINAL_FINAL = _monitor._queue_final_render


def _select_candidate(payload):
    result = _ORIGINAL_SELECT(payload)
    data = _load()
    shot_id = str(payload.get("shot_id") or "")
    output_id = str(payload.get("candidate_id") or "")
    for mission in data.get("missions") or []:
        for shot in mission.get("shots") or []:
            if shot.get("shot_id") == shot_id:
                shot["selected_output_id"] = output_id
                shot["status"] = "selected"
                mission["updated_at"] = _now()
    _save(data)
    return result


def _queue_revision(payload):
    result = _ORIGINAL_REVISE(payload)
    data = _load()
    shot_id = str(payload.get("shot_id") or "")
    instruction = str(payload.get("instruction") or "重新生成一个不同候选")[:500]
    for mission in data.get("missions") or []:
        for shot in mission.get("shots") or []:
            if shot.get("shot_id") != shot_id:
                continue
            revision_no = 1 + len([x for x in shot.get("candidates") or [] if ":R" in str(x.get("key") or "")])
            candidate = {
                "key": f"{shot_id}:R{revision_no:02d}", "index": len(shot.get("candidates") or []) + 1,
                "status": "pending", "attempts": 0, "max_retries": 3, "manual_retries": 0,
                "next_retry_at": "", "started_at": "", "finished_at": "", "last_error": "",
                "output_id": "", "file_url": "", "owner_instruction": instruction, "updated_at": _now(),
            }
            shot.setdefault("candidates", []).append(candidate)
            shot["status"] = "revision_pending"
            mission["status"] = "running"
            mission["updated_at"] = _now()
            mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "revision_queued", "detail": f"镜头{shot.get('order')} 已追加一个修改候选。"})
    _save(data)
    return result


def _queue_final_render(payload):
    result = _ORIGINAL_FINAL(payload)
    data = _load()
    project_id = str(payload.get("project_id") or "")
    mission = _mission_for_project(data, project_id)
    if mission:
        mission["stage"] = "final_render"
        mission["status"] = "awaiting_final_render"
        mission["updated_at"] = _now()
        mission.setdefault("content_card", {})["review_status"] = "镜头已确认"
        mission.setdefault("events", []).insert(0, {"at": _now(), "kind": "final_render_queued", "detail": "已进入配音、字幕、剪辑和整片质检阶段。"})
        _save(data)
    return result


_center.import_director_plan = _mission_import
_monitor._select_candidate = _select_candidate
_monitor._queue_revision = _queue_revision
_monitor._queue_final_render = _queue_final_render


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > 128 * 1024:
        raise ValueError("请求内容不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


if not getattr(_server.DashboardHandler, "_kz_production_mission_patched", False):
    _get = _server.DashboardHandler.do_GET
    _post = _server.DashboardHandler.do_POST

    def _do_get(self):
        path = urlsplit(self.path).path
        if path == "/api/production-missions/current":
            self._json_ok(current_mission()); return
        if path == "/api/production-missions":
            self._json_ok(list_missions()); return
        return _get(self)

    def _do_post(self):
        path = urlsplit(self.path).path
        actions = {
            "/api/production-missions/resume": resume,
            "/api/production-missions/pause": pause,
            "/api/production-missions/next": claim_next,
            "/api/production-missions/checkpoint": checkpoint,
            "/api/production-missions/fail": fail,
            "/api/production-missions/retry": retry_failed,
            "/api/production-missions/card": update_card,
        }
        action = actions.get(path)
        if not action:
            return _post(self)
        if not _origin_allowed(self):
            self._json_error(403, "仅允许本机生产执行器操作"); return
        try:
            self._json_ok(action(_read_body(self)), code=200)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json_error(400, error)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_production_mission_patched = True


_recover_interrupted()
_ensure_latest_mission()
