"""#99 full shot editor for real production projects.

Supports add/delete/edit/split/merge/reorder/candidate-count changes and targeted
regeneration. Any generation-changing operation rotates only the affected shot
ID, invalidates that shot's old candidates/finals, and rebuilds the durable
mission while unchanged shot IDs can reuse their existing real candidates.
"""
from __future__ import annotations

import json
from copy import deepcopy
from urllib.parse import urlsplit

from backend import kz_local_control_patch as _video
from backend import production_mission_patch as _mission
from backend import server
from promotion import ai_production_center as _center

_INSTALLED = False


def _read_json(handler, limit=128 * 1024):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > limit:
        raise ValueError("请求内容为空或超过限制")
    return json.loads(handler.rfile.read(length) or b"{}")


def _origin_allowed(handler):
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}


def _project_shots(data, project_id):
    return sorted([x for x in data.get("storyboards") or [] if x.get("project_id") == project_id], key=lambda x: int(x.get("order") or 0))


def _find_shot(data, shot_id):
    shot = next((x for x in data.get("storyboards") or [] if x.get("id") == shot_id), None)
    if not shot:
        raise ValueError("没有找到镜头")
    return shot


def _renumber(data, project_id):
    for index, shot in enumerate(_project_shots(data, project_id), 1):
        shot["order"] = index
        shot["updated_at"] = _center.now_iso()


def _invalidate_final(data, project_id, reason):
    for output in data.get("outputs") or []:
        if output.get("project_id") != project_id or output.get("kind") != "最终成片":
            continue
        output["kind"] = "历史最终成片"
        output["status"] = "分镜已修改 · 需重新合成"
        output["stale_reason"] = reason
        output["updated_at"] = _center.now_iso()
    for task in data.get("tasks") or []:
        if task.get("project_id") == project_id and task.get("kind") == "完整成片合成" and str(task.get("status") or "") not in {"取消", "已取消"}:
            task["status"] = "已失效"
            task["detail"] = "分镜结构已修改，原成片任务不再代表当前项目。"
            task["updated_at"] = _center.now_iso()
    project = next((x for x in data.get("projects") or [] if x.get("id") == project_id), None)
    if project:
        project["status"] = "分镜已修改 · 待补齐候选"
        project.pop("final_output_id", None)
        project.pop("final_output_url", None)
        project["updated_at"] = _center.now_iso()


def _invalidate_shot_outputs(data, shot_id, reason):
    for output in data.get("outputs") or []:
        if output.get("shot_id") != shot_id:
            continue
        if output.get("kind") == "镜头候选视频":
            output["kind"] = "历史候选视频"
            output["status"] = "已失效"
            output["selected"] = False
            output["stale_reason"] = reason
            output["updated_at"] = _center.now_iso()
    for task in data.get("tasks") or []:
        if task.get("shot_id") == shot_id and "候选" in str(task.get("kind") or ""):
            task["status"] = "已失效"
            task["detail"] = reason
            task["updated_at"] = _center.now_iso()


def _reset_mission(project_id):
    missions = _mission._load()
    before = len(missions.get("missions") or [])
    missions["missions"] = [x for x in (missions.get("missions") or []) if x.get("project_id") != project_id]
    if len(missions["missions"]) != before:
        _mission._save(missions)


def _new_shot(project_id, order, seed=None):
    seed = seed or {}
    return {
        "id": _center._id("SHOT"), "project_id": project_id, "order": int(order),
        "purpose": str(seed.get("purpose") or "新镜头")[:160],
        "narration": str(seed.get("narration") or "")[:500],
        "duration_seconds": max(1.0, min(float(seed.get("duration_seconds") or 4), 12.0)),
        "shot_type": str(seed.get("shot_type") or "中景")[:60],
        "motion": str(seed.get("motion") or "稳定")[:80],
        "candidate_count": max(1, min(int(seed.get("candidate_count") or 1), 4)),
        "status": "待候选生成", "source": "#99 镜头编辑器",
        "character": str(seed.get("character") or "")[:100],
        "scene": str(seed.get("scene") or "")[:120],
        "props": [str(x)[:80] for x in (seed.get("props") or [])[:8]],
        "action": str(seed.get("action") or "")[:240],
        "generation_method": str(seed.get("generation_method") or "真实素材优先")[:80],
        "consistency_locks": [str(x)[:120] for x in (seed.get("consistency_locks") or [])[:10]],
        "negative_constraints": [str(x)[:120] for x in (seed.get("negative_constraints") or [])[:12]],
        "asset_ids": list(seed.get("asset_ids") or [])[:12],
        "created_at": _center.now_iso(), "updated_at": _center.now_iso(),
    }


def _commit(data, project_id, kind, target_id, detail, reset=True):
    _renumber(data, project_id)
    _invalidate_final(data, project_id, detail)
    _center._audit(data, kind, target_id, detail)
    _center._save(data)
    if reset:
        _reset_mission(project_id)
    return {"ok": True, "project_id": project_id, "shots": _project_shots(_center._load(), project_id)}


def add_shot(payload):
    data = _center._load()
    project_id = str(payload.get("project_id") or "").strip()
    if not any(x.get("id") == project_id for x in data.get("projects") or []):
        raise ValueError("没有找到项目")
    after = str(payload.get("after_shot_id") or "").strip()
    shots = _project_shots(data, project_id)
    insert_at = len(shots) + 1
    if after:
        current = _find_shot(data, after)
        if current.get("project_id") != project_id:
            raise ValueError("镜头不属于当前项目")
        insert_at = int(current.get("order") or len(shots)) + 1
    for shot in shots:
        if int(shot.get("order") or 0) >= insert_at:
            shot["order"] = int(shot.get("order") or 0) + 1
    created = _new_shot(project_id, insert_at, payload.get("shot") if isinstance(payload.get("shot"), dict) else {})
    data.setdefault("storyboards", []).append(created)
    result = _commit(data, project_id, "shot_added_v99", created["id"], f"#99 新增镜头 {insert_at}；只需补生成新镜头候选。")
    result["shot"] = created
    return result


def delete_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    project_id = shot.get("project_id")
    if len(_project_shots(data, project_id)) <= 1:
        raise ValueError("至少保留一个镜头")
    old_id = shot.get("id")
    _invalidate_shot_outputs(data, old_id, "镜头已被#99删除")
    data["storyboards"] = [x for x in data.get("storyboards") or [] if x.get("id") != old_id]
    return _commit(data, project_id, "shot_deleted_v99", old_id, "#99 删除镜头；其他未修改镜头的真实候选继续保留。")


def _replace_with_new_id(data, shot, patch, reason):
    old_id = shot.get("id")
    project_id = shot.get("project_id")
    _invalidate_shot_outputs(data, old_id, reason)
    updated = deepcopy(shot)
    updated.update(patch)
    updated["id"] = _center._id("SHOT")
    updated["status"] = "待候选生成"
    updated["source"] = "#99 镜头编辑器"
    updated["regenerated_from_shot_id"] = old_id
    updated["updated_at"] = _center.now_iso()
    index = data["storyboards"].index(shot)
    data["storyboards"][index] = updated
    return project_id, old_id, updated


def edit_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else {}
    allowed_text = {"purpose": 160, "narration": 500, "shot_type": 60, "motion": 80, "character": 100, "scene": 120, "action": 240, "generation_method": 80}
    clean = {}
    for key, limit in allowed_text.items():
        if key in patch:
            clean[key] = str(patch.get(key) or "").strip()[:limit]
    if "duration_seconds" in patch:
        clean["duration_seconds"] = max(1.0, min(float(patch.get("duration_seconds") or 4), 12.0))
    if "candidate_count" in patch:
        clean["candidate_count"] = max(1, min(int(patch.get("candidate_count") or 1), 4))
    for key, limit, count in (("props", 80, 8), ("consistency_locks", 120, 10), ("negative_constraints", 120, 12)):
        if key in patch:
            values = patch.get(key) if isinstance(patch.get(key), list) else []
            clean[key] = [str(x).strip()[:limit] for x in values[:count] if str(x).strip()]
    if not clean:
        raise ValueError("没有可保存的镜头修改")
    project_id, old_id, updated = _replace_with_new_id(data, shot, clean, "镜头内容已修改，原候选不再代表当前镜头")
    result = _commit(data, project_id, "shot_edited_v99", updated["id"], f"#99 已修改单镜头；旧镜头 {old_id} 候选转为历史记录，其他镜头不重跑。")
    result["shot"] = updated
    return result


def regenerate_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    patch = {}
    if payload.get("candidate_count") is not None:
        patch["candidate_count"] = max(1, min(int(payload.get("candidate_count") or 1), 4))
    project_id, old_id, updated = _replace_with_new_id(data, shot, patch, "老板要求单镜头重新生成")
    result = _commit(data, project_id, "shot_regenerate_v99", updated["id"], f"#99 仅重生成当前镜头；旧镜头 {old_id} 已保留为历史候选。")
    result["shot"] = updated
    return result


def move_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    project_id = shot.get("project_id")
    shots = _project_shots(data, project_id)
    current = shots.index(shot)
    direction = str(payload.get("direction") or "").lower()
    if "order" in payload:
        target = max(0, min(len(shots) - 1, int(payload.get("order") or 1) - 1))
    else:
        target = current - 1 if direction == "up" else current + 1
        target = max(0, min(len(shots) - 1, target))
    if target == current:
        return {"ok": True, "project_id": project_id, "shots": shots}
    shots[current], shots[target] = shots[target], shots[current]
    for index, item in enumerate(shots, 1):
        item["order"] = index
    return _commit(data, project_id, "shot_reordered_v99", shot.get("id"), "#99 已调整镜头顺序；真实候选保留，最终成片需重新合成。")


def split_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    project_id = shot.get("project_id")
    old_id = shot.get("id")
    _invalidate_shot_outputs(data, old_id, "原镜头已拆分")
    narration = str(shot.get("narration") or shot.get("purpose") or "")
    at = int(payload.get("at") or max(1, len(narration) // 2))
    at = max(1, min(len(narration) - 1, at)) if len(narration) > 1 else 1
    first_text, second_text = narration[:at].strip("，,。；; "), narration[at:].strip("，,。；; ")
    total_duration = max(2.0, float(shot.get("duration_seconds") or 4))
    first = _new_shot(project_id, shot.get("order"), {**shot, "narration": first_text, "purpose": first_text or str(shot.get("purpose") or "")[:80], "duration_seconds": total_duration / 2})
    second = _new_shot(project_id, int(shot.get("order") or 0) + 1, {**shot, "narration": second_text, "purpose": second_text or "承接上一镜头", "duration_seconds": total_duration / 2})
    idx = data["storyboards"].index(shot)
    data["storyboards"][idx:idx + 1] = [first, second]
    return _commit(data, project_id, "shot_split_v99", old_id, "#99 已把一个镜头拆成两个新镜头；其他镜头候选保留。")


def merge_shot(payload):
    data = _center._load()
    shot = _find_shot(data, str(payload.get("shot_id") or ""))
    project_id = shot.get("project_id")
    shots = _project_shots(data, project_id)
    index = shots.index(shot)
    if index >= len(shots) - 1:
        raise ValueError("最后一个镜头没有下一个镜头可合并")
    other = shots[index + 1]
    _invalidate_shot_outputs(data, shot.get("id"), "镜头已合并")
    _invalidate_shot_outputs(data, other.get("id"), "镜头已合并")
    narration = "，".join(x for x in (str(shot.get("narration") or "").strip(), str(other.get("narration") or "").strip()) if x)
    merged = _new_shot(project_id, shot.get("order"), {
        **shot,
        "purpose": (str(shot.get("purpose") or "") + " / " + str(other.get("purpose") or "")).strip(" /")[:160],
        "narration": narration[:500],
        "duration_seconds": min(12.0, float(shot.get("duration_seconds") or 4) + float(other.get("duration_seconds") or 4)),
        "action": (str(shot.get("action") or "") + "；" + str(other.get("action") or "")).strip("；")[:240],
        "consistency_locks": list(dict.fromkeys(list(shot.get("consistency_locks") or []) + list(other.get("consistency_locks") or [])))[:10],
    })
    data["storyboards"] = [x for x in data["storyboards"] if x.get("id") not in {shot.get("id"), other.get("id")}]
    data["storyboards"].append(merged)
    return _commit(data, project_id, "shot_merged_v99", merged.get("id"), "#99 已合并相邻镜头；只需生成合并后的新镜头候选。")


def editor_status():
    data = _center._load()
    project = (data.get("projects") or [None])[0]
    shots = _project_shots(data, project.get("id")) if project else []
    return {"ok": True, "project": project, "shots": shots, "actions": ["add", "delete", "edit", "split", "merge", "move", "regenerate"]}


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    old_get = server.DashboardHandler.do_GET
    old_post = server.DashboardHandler.do_POST
    actions = {
        "/api/content-final/shot/add": add_shot,
        "/api/content-final/shot/delete": delete_shot,
        "/api/content-final/shot/edit": edit_shot,
        "/api/content-final/shot/split": split_shot,
        "/api/content-final/shot/merge": merge_shot,
        "/api/content-final/shot/move": move_shot,
        "/api/content-final/shot/regenerate": regenerate_shot,
    }

    def do_get(handler):
        if urlsplit(handler.path).path == "/api/content-final/shot-editor":
            handler._json_ok(editor_status())
            return
        return old_get(handler)

    def do_post(handler):
        action = actions.get(urlsplit(handler.path).path)
        if not action:
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机编辑分镜")
            return
        try:
            handler._json_ok(action(_read_json(handler)))
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_shot_editor_v99 = True
    _INSTALLED = True


install()
