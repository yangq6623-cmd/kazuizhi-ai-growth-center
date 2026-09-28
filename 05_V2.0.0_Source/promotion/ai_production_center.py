"""Stage-one foundation for the standalone AI Content Production Center.

This module deliberately records production intent and local assets without
pretending that a model task, a rendered file, or an external publication has
already happened.  It is independent from growth campaigns so production can
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


def create_project(payload):
    data = _load()
    project = {
        "id": _id("AIP"), "created_at": now_iso(),
        "name": _clean(payload.get("name"), "项目名称", 100),
        "script": _clean(payload.get("script"), "文案", 6000, False),
        "ratio": _clean(payload.get("ratio") or "9:16", "画幅", 10),
        "status": "草稿", "default_character_id": "", "default_scene_id": "",
        "default_voice_id": "", "owner_note": _clean(payload.get("owner_note"), "项目说明", 500, False),
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
    task = {
        "id": _id("TASK"), "project_id": project["id"], "shot_id": shot_id,
        "kind": "镜头候选生成", "executor": "本地 Router（按显存排队）",
        "status": "待本地执行器", "progress": 0, "created_at": now_iso(),
        "detail": "仅创建本地执行任务；候选文件生成后才会显示可审核。",
    }
    data["tasks"].insert(0, task); shot["status"] = "候选生成已排队"
    _audit(data, "candidate_queued", shot_id, "已创建候选生成任务，尚无候选文件或对外发布。")
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
