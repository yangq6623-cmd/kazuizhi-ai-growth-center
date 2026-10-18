"""R8-18 #75 short-video acceptance patch.

Adds a truthful 5-second/2-shot controlled-test path without disturbing normal
15/30/45/60 second production:
- expose 5s and 10s options in Simple Mode;
- make <=8s director guidance use two shots, and make an explicit "2 shots"
  request a hard two-shot contract;
- when a project really has two shots and at least two preferred/local images,
  route the two most recent references chronologically: shot 1 -> image 1,
  shot 2 -> image 2. This avoids silently using the same first image for both
  shots and gives continuity testing a clean input contract.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from backend import dynamic_director_policy_patch as _director
from backend import kz_local_control_patch as _video
from backend import server
from promotion import ai_production_center as _center

_INSTALLED = False
_ORIGINAL_GET = server.DashboardHandler.do_GET
_ORIGINAL_SUGGESTED_RANGE = _director._suggested_range
_ORIGINAL_AUGMENT = _director.augment_director_payload
_ORIGINAL_ASSET_FOR_SHOT = _video._asset_for_shot

_DURATION_OPTIONS_OLD = (
    '<option value="15 秒">15 秒</option>'
    '<option value="30 秒" selected>30 秒</option>'
)
_DURATION_OPTIONS_NEW = (
    '<option value="5 秒">5 秒（双镜头测试）</option>'
    '<option value="10 秒">10 秒（短视频测试）</option>'
    '<option value="15 秒">15 秒</option>'
    '<option value="30 秒" selected>30 秒</option>'
)


def _seconds_from_text(text, default=30):
    match = re.search(r"(?:目标时长|视频时长|时长)?\s*[:：]?\s*(\d{1,3})\s*秒", str(text or ""))
    try:
        return int(match.group(1)) if match else int(default)
    except (TypeError, ValueError):
        return int(default)


def _short_range(text):
    seconds = _seconds_from_text(text)
    if seconds <= 8:
        return "2"
    if seconds <= 12:
        return "2-4"
    return _ORIGINAL_SUGGESTED_RANGE(text)


def _wants_exact_two(text):
    value = str(text or "")
    if _seconds_from_text(value, 999) > 8:
        return False
    patterns = (
        r"共\s*2\s*个.*镜头",
        r"2\s*个.*连续镜头",
        r"两个.*连续镜头",
        r"两个.*镜头",
        r"镜头\s*1.*镜头\s*2",
    )
    return any(re.search(pattern, value, flags=re.S) for pattern in patterns)


def _augment_short_contract(payload):
    cloned = _ORIGINAL_AUGMENT(payload)
    if not isinstance(cloned, dict):
        return cloned
    messages = cloned.get("messages")
    if not isinstance(messages, list):
        return cloned
    combined = "\n".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))
    if not _wants_exact_two(combined):
        return cloned

    contract = (
        "\n\n【5秒双镜头验收合同】\n"
        "这是受控连续性测试，不是长视频。必须严格输出2个镜头，禁止增加第3个镜头。\n"
        "镜头1与镜头2总时长约5秒，每个约2-3秒；shot_order只能为1、2。\n"
        "镜头2必须承接镜头1结束动作，保持同一人物、服装、场景、设备、工具、光线方向。\n"
        "本轮每镜头只需要1个候选（candidate_count=1），目的是测动作连续性，不是堆候选数量。\n"
        "旁白只写观众会听到的自然口语，禁止出现镜头、导演、展示步骤、专业判断、CTA等制作术语。\n"
        "输出仍必须符合原接口JSON结构。"
    )
    result = dict(cloned)
    copied = [dict(x) if isinstance(x, dict) else x for x in messages]
    if copied and isinstance(copied[-1], dict):
        copied[-1]["content"] = str(copied[-1].get("content") or "") + contract
    result["messages"] = copied
    return result


def _asset_time(asset):
    return str(asset.get("uploaded_at") or asset.get("created_at") or "")


def _two_shot_asset(shot):
    data = _center._load()
    project_id = str(shot.get("project_id") or "")
    project_shots = sorted(
        [x for x in (data.get("storyboards") or []) if str(x.get("project_id") or "") == project_id],
        key=lambda x: int(x.get("order") or 0),
    )
    if len(project_shots) != 2:
        return _ORIGINAL_ASSET_FOR_SHOT(shot)

    preferred = set(shot.get("asset_ids") or [])
    images = _video._recent_image_assets(data)
    source = [x for x in images if x.get("id") in preferred] if preferred else list(images)
    if len(source) < 2:
        return _ORIGINAL_ASSET_FOR_SHOT(shot)

    # Only use the two newest references for a two-shot controlled test, then
    # restore chronological order so the first uploaded reference feeds shot 1.
    refs = sorted(source, key=_asset_time)[-2:]
    order = int(shot.get("order") or 1)
    chosen = refs[0] if order <= 1 else refs[1]
    return _video._ensure_comfy_input(chosen, data)


def _serve_short_duration_js(handler):
    path = urlsplit(handler.path).path
    if path not in {"/content-studio-simple.js", "/web/content-studio-simple.js"}:
        return False
    web_file = Path(__file__).resolve().parents[1] / "web" / "content-studio-simple.js"
    if not web_file.is_file():
        return False
    source = web_file.read_text(encoding="utf-8")
    if _DURATION_OPTIONS_OLD in source:
        source = source.replace(_DURATION_OPTIONS_OLD, _DURATION_OPTIONS_NEW, 1)
    elif 'value="5 秒"' not in source:
        source = source.replace(
            '<option value="15 秒">15 秒</option>',
            '<option value="5 秒">5 秒（双镜头测试）</option>'
            '<option value="10 秒">10 秒（短视频测试）</option>'
            '<option value="15 秒">15 秒</option>',
            1,
        )
    payload = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(payload)
    return True


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    def do_get(handler):
        if _serve_short_duration_js(handler):
            return
        return _ORIGINAL_GET(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_short_video_test_patch = True
    _director._suggested_range = _short_range
    _director.augment_director_payload = _augment_short_contract
    _video._asset_for_shot = _two_shot_asset
    _INSTALLED = True


install()
