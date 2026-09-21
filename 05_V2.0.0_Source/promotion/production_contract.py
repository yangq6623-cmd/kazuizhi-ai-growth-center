"""Strict machine contract between ChatGPT strategy and the local R8 video factory.

ChatGPT remains the only planning/creative controller.  This module does not
create topics, scripts or editing decisions.  It only validates and normalizes
ChatGPT's structured production plan before local programs are allowed to act.
"""

from __future__ import annotations

from copy import deepcopy


SCHEMA = "kazuizhi-content-production/v1"
ALLOWED_PLATFORMS = {"抖音", "快手", "小红书", "视频号", "微博", "B站", "通用"}
ALLOWED_SOURCES = {"local_real", "licensed_external", "ai_generated", "info_card", "brand_card"}
DEFAULT_FALLBACK = ["local_real", "licensed_external", "ai_generated", "info_card"]


def _text(value, label, limit, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{label}不能为空")
    if len(value) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return value


def _number(value, label, minimum, maximum, default):
    try:
        result = float(default if value in (None, "") else value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是数字") from None
    if result < minimum or result > maximum:
        raise ValueError(f"{label}必须在{minimum}到{maximum}之间")
    return result


def _source_chain(value, required_real=False):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        value = []
    chain = []
    for item in value:
        item = str(item or "").strip()
        if item in ALLOWED_SOURCES and item not in chain:
            chain.append(item)
    if not chain:
        chain = list(DEFAULT_FALLBACK)
    if required_real:
        # A true repair operation/customer case must never silently fall back to
        # synthetic footage represented as real.  An information card may replace
        # the shot, but synthetic media can only be used as an explicitly labelled
        # explanation/diagram.
        chain = [x for x in chain if x != "ai_generated"]
        if "local_real" not in chain:
            chain.insert(0, "local_real")
        if "licensed_external" not in chain:
            chain.append("licensed_external")
        if "info_card" not in chain:
            chain.append("info_card")
    return chain


def normalize_contract(payload, campaign=None):
    """Validate one ChatGPT production plan and return a stable executable shape."""
    if not isinstance(payload, dict):
        raise ValueError("ChatGPT生产方案必须是对象")
    raw = deepcopy(payload)
    schema = str(raw.get("schema") or SCHEMA).strip()
    if schema != SCHEMA:
        raise ValueError("ChatGPT生产方案schema不兼容")

    campaign_id = _text(raw.get("campaign_id") or (campaign or {}).get("id"), "增长ID", 64)
    objective = _text(raw.get("objective") or (campaign or {}).get("goal"), "经营目标", 240)
    topic = _text(raw.get("topic") or (campaign or {}).get("title"), "选题", 160)
    pain_point = _text(raw.get("pain_point") or (campaign or {}).get("evidence"), "用户痛点", 500)
    script = _text(raw.get("script"), "深层脚本", 6000)

    platforms = raw.get("target_platforms") or ["通用"]
    if isinstance(platforms, str):
        platforms = [platforms]
    if not isinstance(platforms, list):
        raise ValueError("目标平台必须是数组")
    target_platforms = []
    for platform in platforms[:8]:
        platform = str(platform or "").strip()
        if platform not in ALLOWED_PLATFORMS:
            raise ValueError(f"不支持的平台：{platform}")
        if platform not in target_platforms:
            target_platforms.append(platform)
    if not target_platforms:
        target_platforms = ["通用"]

    titles = raw.get("titles") or []
    if isinstance(titles, str):
        titles = [titles]
    if not isinstance(titles, list):
        raise ValueError("标题必须是数组")
    titles = [_text(value, "标题", 120) for value in titles[:8]]
    if not titles:
        titles = [topic]

    storyboard = raw.get("storyboard") or raw.get("edl")
    if not isinstance(storyboard, list) or not storyboard:
        raise ValueError("ChatGPT生产方案必须包含至少一个分镜")
    if len(storyboard) > 20:
        raise ValueError("单条视频最多20个分镜")

    shots = []
    for index, raw_shot in enumerate(storyboard, 1):
        if not isinstance(raw_shot, dict):
            raise ValueError(f"第{index}个分镜格式不正确")
        required_real = bool(raw_shot.get("required_real"))
        shot_id = _text(raw_shot.get("shot_id") or f"S{index:02d}", "镜头ID", 32)
        purpose = _text(raw_shot.get("purpose") or raw_shot.get("description"), "镜头目的", 300)
        narration = _text(raw_shot.get("narration"), "镜头口播", 800, False)
        subtitle = _text(raw_shot.get("subtitle") or narration, "镜头字幕", 300, False)
        query = _text(raw_shot.get("material_query") or raw_shot.get("query") or purpose,
                      "素材检索词", 300)
        source_chain = _source_chain(raw_shot.get("source_preference") or raw_shot.get("fallback_chain"), required_real)
        synthetic_disclosure = _text(
            raw_shot.get("synthetic_disclosure") or ("AI辅助示意" if "ai_generated" in source_chain else ""),
            "AI素材标识", 80, False,
        )
        shots.append({
            "shot_id": shot_id,
            "order": index,
            "purpose": purpose,
            "duration_seconds": _number(raw_shot.get("duration_seconds"), "镜头时长", 1, 15, 3),
            "narration": narration,
            "subtitle": subtitle,
            "material_query": query,
            "required_real": required_real,
            "source_preference": source_chain,
            "synthetic_disclosure": synthetic_disclosure,
            "status": "等待素材路由",
            "selected_source": None,
            "selected_asset_id": None,
            "attempts": 0,
            "last_error": None,
        })

    output = raw.get("output") if isinstance(raw.get("output"), dict) else {}
    width = int(_number(output.get("width"), "输出宽度", 720, 2160, 1080))
    height = int(_number(output.get("height"), "输出高度", 720, 3840, 1920))
    fps = int(_number(output.get("fps"), "输出帧率", 24, 60, 30))
    duration_target = int(_number(
        raw.get("duration_target") or output.get("duration_seconds"), "目标时长", 10, 120,
        min(60, max(10, round(sum(x["duration_seconds"] for x in shots) + 5))),
    ))

    voice = raw.get("voice") if isinstance(raw.get("voice"), dict) else {}
    subtitle = raw.get("subtitle") if isinstance(raw.get("subtitle"), dict) else {}
    cover = raw.get("cover") if isinstance(raw.get("cover"), dict) else {}
    qc = raw.get("qc") if isinstance(raw.get("qc"), dict) else {}

    return {
        "schema": SCHEMA,
        "version": max(1, int(raw.get("version") or 1)),
        "campaign_id": campaign_id,
        "objective": objective,
        "target_platforms": target_platforms,
        "topic": topic,
        "pain_point": pain_point,
        "titles": titles,
        "script": script,
        "storyboard": shots,
        "voice": {
            "enabled": bool(voice.get("enabled", True)),
            "profile": _text(voice.get("profile") or "卡嘴子专业中文声线", "配音配置", 120),
        },
        "subtitle": {
            "enabled": bool(subtitle.get("enabled", True)),
            "style": _text(subtitle.get("style") or "竖屏大字安全区", "字幕样式", 120),
        },
        "cover": {
            "title": _text(cover.get("title") or titles[0], "封面标题", 120),
            "subtitle": _text(cover.get("subtitle"), "封面副标题", 160, False),
        },
        "cta": _text(raw.get("cta") or "通过小程序提交需求，等待师傅报价", "行动提示", 160),
        "output": {
            "width": width,
            "height": height,
            "fps": fps,
            "container": "mp4",
            "codec": "h264",
            "duration_seconds": duration_target,
        },
        "qc": {
            "machine": qc.get("machine") or ["playable", "non_empty", "video_stream", "correct_dimensions"],
            "chatgpt": qc.get("chatgpt") or ["goal_alignment", "truthfulness", "script_storyboard_match", "platform_fit"],
            "owner_review_required": True,
        },
        "material_policy": {
            "local_material_optional": True,
            "quality_first": True,
            "never_fake_real_case": True,
            "missing_material_must_not_block": True,
        },
    }
