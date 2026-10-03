"""Stage-one foundation for the standalone AI Content Production Center.

This module deliberately records production intent and local assets without
pretending that a model task, a rendered file, or an external publication has
already happened. It is independent from growth campaigns so production can
scale without turning the operations dashboard into a form dump.
"""
from __future__ import annotations

import re
from uuid import uuid4

from core.storage import now_iso, read_json, write_json


CENTER_FILE = "r8/ai_content_center.json"
ASSET_TYPES = ("人物", "物品", "场景", "声音", "真实素材", "品牌物料")
RIGHTS = ("本人或公司自有", "已取得授权", "虚拟资产", "待确认")
MODEL_ROUTES = (
    ("脚本与基础执行", "Qwen3 8B", "本地 Router"),
    ("分镜逻辑与风险检查", "DeepSeek-R1 8B", "本地 Router"),
    ("素材识别与标注", "Qwen3-VL 8B", "本地 Router"),
    ("图片 / 视频 / 配音 / 剪辑", "ComfyUI / ChatTTS / FFmpeg", "按任务加载"),
)


def _default():
    return {
        "schema_version": 1,
        "projects": [], "assets": [], "storyboards": [], "tasks": [],
        "outputs": [], "events": [],
    }


def _load():
    data = read_json(CENTER_FILE, _default())
    if not isinstance(data, dict):
        data = _default()
    for key, value in _default().items():
        data.setdefault(key, value)
    return data


def _save(data):
    return write_json(CENTER_FILE, data)


def _id(prefix):
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _clean(value, label, limit=300, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{label}不能为空")
    if len(value) > limit:
        raise ValueError(f"{label}不能超过{limit}个字符")
    return value


def _find(items, identifier, label):
    for item in items:
        if item.get("id") == identifier:
            return item
    raise ValueError(f"未找到{label}")


def _audit(data, kind, identifier, detail):
    data["events"].insert(0, {
        "id": _id("AUDIT"), "created_at": now_iso(), "kind": kind,
        "target_id": identifier, "detail": detail,
    })


def _text_list(value, label, limit=8, item_limit=160):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:limit]:
        text = _clean(item, label, item_limit, False)
        if text:
            result.append(text)
    return result


def create_project(payload):
    data = _load()
    project = {
        "id": _id("AIP"), "created_at": now_iso(),
        "name": _clean(payload.get("name"), "项目名称", 100),
        "script": _clean(payload.get("script"), "文案", 6000, False),
        "ratio": _clean(payload.get("ratio") or "9:16", "画幅", 10),
        "status": "草稿", "default_character_id": "", "default_scene_id": "",
        "default_voice_id": "", "owner_note": _clean(payload.get("owner_note"), "项目说明", 500, False),
        "reference_id": _clean(payload.get("reference_id"), "参考内容ID", 80, False),
        "creative_id": _clean(payload.get("creative_id"), "创意ID", 80, False),
        "director_plan_id": _clean(payload.get("director_plan_id"), "导演方案ID", 80, False),
    }
    data["projects"].insert(0, project)
    _audit(data, "project_created", project["id"], "已建立本地内容项目；尚未生成或发布。")
    _save(data)
    return project


def add_asset(payload):
    data = _load()
    asset_type = _clean(payload.get("asset_type"), "资产类型", 20)
    if asset_type not in ASSET_TYPES:
        raise ValueError("资产类型不在允许范围内")
    rights = _clean(payload.get("rights") or "待确认", "授权状态", 30)
    if rights not in RIGHTS:
        raise ValueError("授权状态不正确")
    asset = {
        "id": _id("ASSET"), "created_at": now_iso(), "asset_type": asset_type,
        "name": _clean(payload.get("name"), "资产名称", 100),
        "rights": rights, "tags": _clean(payload.get("tags"), "标签", 160, False),
        "note": _clean(payload.get("note"), "说明", 500, False), "enabled": rights != "待确认",
    }
    data["assets"].insert(0, asset)
    _audit(data, "asset_registered", asset["id"], f"登记{asset_type}资产；授权：{rights}。")
    _save(data)
    return asset


def _sentences(script):
    parts = [x.strip() for x in re.split(r"[。！？；\n]+", script or "") if x.strip()]
    if not parts:
        return []
    return parts[:8]


def create_storyboard_draft(payload):
    data = _load()
    project_id = _clean(payload.get("project_id"), "项目ID", 64)
    project = _find(data["projects"], project_id, "项目")
    script = _clean(payload.get("script") or project.get("script"), "文案", 6000)
    project["script"] = script
    existing = [x for x in data["storyboards"] if x.get("project_id") == project_id]
    data["storyboards"] = [x for x in data["storyboards"] if x.get("project_id") != project_id]
    shots = []
    for index, sentence in enumerate(_sentences(script), 1):
        shot = {
            "id": _id("SHOT"), "project_id": project_id, "order": index,
            "purpose": sentence[:70], "narration": sentence, "duration_seconds": 5,
            "shot_type": "中景", "motion": "稳定跟拍", "candidate_count": 2,
            "status": "待 ChatGPT 总控确认", "source": "本地结构草稿",
            "character": "", "scene": "", "props": [], "action": "",
            "generation_method": "待导演确认", "consistency_locks": [],
            "negative_constraints": [],
        }
        data["storyboards"].append(shot); shots.append(shot)
    project["status"] = "等待 ChatGPT 总控确认"
    task = {
        "id": _id("TASK"), "project_id": project_id, "kind": "分镜合同确认",
        "executor": "ChatGPT 总控 → 本地 Router", "status": "待总控确认",
        "progress": 0, "created_at": now_iso(),
        "detail": f"已生成 {len(shots)} 条本地结构草稿；尚未调用生成模型。",
    }
    data["tasks"].insert(0, task)
    _audit(data, "storyboard_drafted", project_id, f"更新分镜草稿 {len(existing)}→{len(shots)} 条，等待总控确认。")
    _save(data)
    return {"project": project, "storyboards": shots, "task": task}


def import_director_plan(payload):
    """Create one production project from an owner-confirmed AI director plan.

    The endpoint records exact structured shots but still does not claim that
    any image/video candidate or final render exists. Candidate generation is a
    separate explicit task for every shot.
    """
    data = _load()
    raw_shots = payload.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("导演方案至少需要一个镜头")
    if len(raw_shots) > 12:
        raise ValueError("单条导演方案最多导入12个镜头")

    reference_id = _clean(payload.get("reference_id"), "参考内容ID", 80, False)
    creative_id = _clean(payload.get("creative_id"), "创意ID", 80, False)
    director_plan_id = _clean(payload.get("director_plan_id") or _id("DIR"), "导演方案ID", 80)
    project = {
        "id": _id("AIP"), "created_at": now_iso(),
        "name": _clean(payload.get("name"), "项目名称", 100),
        "script": _clean(payload.get("script"), "文案", 6000, False),
        "ratio": _clean(payload.get("ratio") or "9:16", "画幅", 10),
        "status": "分镜已确认", "default_character_id": "", "default_scene_id": "",
        "default_voice_id": "", "owner_note": _clean(payload.get("owner_note"), "项目说明", 500, False),
        "reference_id": reference_id, "creative_id": creative_id,
        "director_plan_id": director_plan_id,
        "director_goal": _clean(payload.get("director_goal"), "视频目标", 80, False),
        "director_style": _clean(payload.get("director_style"), "全片风格", 80, False),
        "director_summary": _clean(payload.get("director_summary"), "导演摘要", 1200, False),
    }
    data["projects"].insert(0, project)

    shots = []
    total_duration = 0.0
    for index, raw in enumerate(raw_shots, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"镜头{index}格式不正确")
        try:
            duration = float(raw.get("duration_seconds") or 4)
        except (TypeError, ValueError):
            duration = 4.0
        duration = max(1.0, min(duration, 12.0))
        try:
            candidate_count = int(raw.get("candidate_count") or 3)
        except (TypeError, ValueError):
            candidate_count = 3
        candidate_count = max(1, min(candidate_count, 4))
        shot = {
            "id": _id("SHOT"), "project_id": project["id"], "order": index,
            "purpose": _clean(raw.get("purpose") or f"镜头 {index}", "镜头目的", 160),
            "narration": _clean(raw.get("narration"), "台词/旁白", 500, False),
            "duration_seconds": duration,
            "shot_type": _clean(raw.get("shot_type") or "中景", "景别", 60),
            "motion": _clean(raw.get("motion") or "稳定", "运镜", 80),
            "candidate_count": candidate_count,
            "status": "待候选生成", "source": "AI 导演确认方案",
            "character": _clean(raw.get("character"), "人物", 100, False),
            "scene": _clean(raw.get("scene"), "场景", 120, False),
            "props": _text_list(raw.get("props"), "物品", 8, 80),
            "action": _clean(raw.get("action"), "动作", 240, False),
            "generation_method": _clean(raw.get("generation_method") or "真实素材优先", "生成方式", 80),
            "consistency_locks": _text_list(raw.get("consistency_locks"), "一致性锁", 8, 100),
            "negative_constraints": _text_list(raw.get("negative_constraints"), "负面约束", 10, 120),
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
    task = {
        "id": _id("TASK"), "project_id": project["id"], "kind": "AI 导演分镜导入",
        "executor": "内容创导平台 → AI 内容生产中心", "status": "已完成",
        "progress": 100, "created_at": now_iso(),
        "detail": f"已确认并导入 {len(shots)} 个结构化镜头（约 {total_duration:g} 秒）；尚未生成候选或成片。",
    }
    data["tasks"].insert(0, task)
    _audit(data, "director_plan_imported", project["id"], task["detail"])
    _save(data)
    return {"project": project, "storyboards": shots, "task": task}


def queue_candidate_generation(payload):
    data = _load()
    shot_id = _clean(payload.get("shot_id"), "镜头ID", 64)
    shot = _find(data["storyboards"], shot_id, "镜头")
    project = _find(data["projects"], shot["project_id"], "项目")
    asset_ids = payload.get("asset_ids") if isinstance(payload.get("asset_ids"), list) else []
    assets = [x for x in data["assets"] if x.get("id") in asset_ids]
    blocked = [x.get("name") for x in assets if x.get("rights") == "待确认"]
    if blocked:
        raise ValueError("以下资产尚未确认授权，不能进入候选生成：" + "、".join(blocked))
    count = max(1, min(int(shot.get("candidate_count") or 2), 4))
    task = {
        "id": _id("TASK"), "project_id": project["id"], "shot_id": shot_id,
        "kind": "镜头候选生成", "executor": "本地 Router（按显存排队）",
        "status": "待本地执行器", "progress": 0, "created_at": now_iso(),
        "detail": f"仅创建本地执行任务；计划生成 {count} 个候选，出现真实候选文件后才会显示可审核。",
    }
    data["tasks"].insert(0, task); shot["status"] = "候选生成已排队"
    _audit(data, "candidate_queued", shot_id, f"已创建 {count} 候选生成任务，尚无候选文件或对外发布。")
    _save(data)
    return task


def dashboard():
    data = _load()
    tasks = list(data["tasks"])
    return {
        "schema": "kazuizhi-ai-production-center/v1", "projects": data["projects"],
        "assets": data["assets"], "storyboards": data["storyboards"], "tasks": tasks,
        "outputs": data["outputs"], "events": data["events"][:12],
        "model_routes": [{"work": a, "model": b, "route": c} for a, b, c in MODEL_ROUTES],
        "truth": "草稿、任务、候选、成片和外部发布是五个不同状态；没有本地文件和人工确认，不显示为成片或已发布。",
    }
