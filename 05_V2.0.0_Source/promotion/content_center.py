"""Auditable local-promotion drafts. Nothing in this module publishes content."""

import json
import os
import re
from pathlib import Path

from core.storage import now_iso, read_json, write_json


SAFE_POSITIONING = "专业维修找师傅，生活小事也能发任务"
SEED_KEYWORDS = (
    ("涟水水电工师傅上门服务", "涟水", "水电维修"),
    ("涟水家电维修服务", "涟水", "家电维修"),
    ("淮安取送跑腿服务", "淮安", "跑腿取送"),
    ("淮安上门维修服务", "淮安", "上门维修"),
)
FORBIDDEN_CLAIMS = (
    "人人都能接单", "任何周边人都可以直接接单", "无需审核即可接单", "所有任务都能发布",
    "保证第一", "排名第一", "全网最低", "百分百", "100%", "绝对有效", "最快", "最好",
)


def _text(value, name, maximum=120, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > maximum:
        raise ValueError(f"{name} is too long")
    if any(claim.lower() in value.lower() for claim in FORBIDDEN_CLAIMS):
        raise ValueError("内容包含无法核验或不允许的宣传承诺")
    return value


def _external_keywords():
    explicit = os.environ.get("KAZUIZHI_AI_REPORT_PATH")
    paths = [Path(explicit)] if explicit else []
    paths.append(Path(r"C:\卡嘴子自动化\ai-center\01_本机上报\latest.json"))
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        candidates = payload.get("keywords") or payload.get("keyword_signals") or []
        items = []
        for item in candidates:
            if isinstance(item, str):
                phrase, score, seen = item, None, None
            elif isinstance(item, dict):
                phrase = item.get("keyword") or item.get("text") or item.get("phrase") or item.get("name")
                score, seen = item.get("score"), item.get("last_seen")
            else:
                continue
            phrase = str(phrase or "").strip()
            if phrase and len(phrase) <= 120:
                items.append({"keyword": phrase, "region": "", "category": "", "source": "historical_public_signal",
                              "research_priority": score, "last_seen": seen,
                              "note": "公开搜索研究信号，不代表真实搜索量、排名、订单或收入。"})
        if items:
            return items[:100]
    return []


def list_keywords():
    stored = read_json("promotion/keywords.json", {"items": []}).get("items", [])
    seeded = [{"keyword": k, "region": r, "category": c, "source": "product_strategy_seed",
               "note": "产品方向种子词，不代表搜索量或排名。"} for k, r, c in SEED_KEYWORDS]
    merged, seen = [], set()
    for item in _external_keywords() + stored + seeded:
        key = str(item.get("keyword", "")).strip().lower()
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    return {"status": "available", "items": merged, "count": len(merged),
            "truth_rule": "关键词仅用于研究和内容草稿；不代表搜索量、排名、订单或收入。"}


def add_keyword(payload):
    keyword = _text(payload.get("keyword"), "keyword")
    item = {"keyword": keyword, "region": _text(payload.get("region"), "region", 40, False),
            "category": _text(payload.get("category"), "category", 60, False),
            "source": "owner_input", "created_at": now_iso(),
            "note": "老板手动录入的研究词，不代表搜索量或排名。"}
    data = read_json("promotion/keywords.json", {"items": []})
    items = data.get("items", [])
    if not any(str(x.get("keyword", "")).lower() == keyword.lower() for x in items):
        items.append(item)
        write_json("promotion/keywords.json", {"items": items})
    return item


def _context(payload):
    region = _text(payload.get("region"), "region", 40)
    service = _text(payload.get("service"), "service", 60)
    keyword = _text(payload.get("keyword") or f"{region}{service}服务", "keyword")
    audience = _text(payload.get("audience") or "本地有服务需求的用户", "audience", 100)
    evidence = _text(payload.get("evidence"), "evidence", 300, False)
    return region, service, keyword, audience, evidence


def _save(kind, payload, output):
    record = {"id": now_iso(), "created_at": now_iso(), "kind": kind, "input": payload,
              "execution": "proposal_only", "review_status": "待人工审核", "output": output}
    history = read_json("promotion/history.json", {"items": []})
    history.setdefault("items", []).insert(0, record)
    history["items"] = history["items"][:100]
    write_json("promotion/history.json", history)
    return record


def generate_seo(payload):
    region, service, keyword, audience, evidence = _context(payload)
    output = {
        "title": f"{region}{service}怎么找？服务信息与下单前检查清单",
        "meta_description": f"围绕“{keyword}”整理服务范围、需求描述和下单前核对事项。{SAFE_POSITIONING}。",
        "outline": ["先说明具体需求与服务区域", "核对服务范围、时间与平台审核状态", "发布需求并等待符合条件的服务者响应", "完成后保留真实评价与服务记录"],
        "draft": f"面向{audience}，查找{region}{service}时，建议先写清地点、问题现象和期望时间。平台用于连接本地需求与服务信息，接单能力以平台实际开放、账号审核和任务状态为准。{('可引用的已核验证据：' + evidence) if evidence else '当前没有可核验经营证据，因此不写订单量、排名或效果承诺。'}",
        "review_notes": ["发布前核对服务范围", "不得编造案例、排名、订单量或用户评价", "不得承诺效果或自动接单"],
    }
    return _save("SEO内容草稿", payload, output)


def generate_geo(payload):
    region, service, keyword, audience, evidence = _context(payload)
    output = {
        "landing_page": {"title": f"{region}{service}本地服务信息", "primary_keyword": keyword,
                         "sections": ["服务范围", "适用需求", "发布流程", "审核与安全说明", "常见问题"]},
        "local_profile": ["统一品牌名、服务区域和联系方式", "只填写实际覆盖区域和营业状态", "保持地图、官网与平台资料一致"],
        "faq": [f"{region}{service}如何发布需求？", "哪些任务需要平台审核？", "服务范围和响应时间如何确认？"],
        "measurement": ["记录页面访问来源", "区分有效咨询和已核验订单", "按周复核关键词信号，不将排名变化当作经营结果"],
        "audience": audience, "evidence_used": evidence or "无；方案不包含效果数据或排名承诺",
    }
    return _save("GEO本地优化建议", payload, output)


def generate_ad(payload):
    region, service, keyword, audience, evidence = _context(payload)
    output = {
        "positioning": SAFE_POSITIONING,
        "variants": [
            {"headline": f"{region}{service}需求，可在平台发布", "body": f"写清地点、需求和期望时间，查看平台实际开放的服务信息。接单以账号审核和任务状态为准。"},
            {"headline": f"{service}与本地生活任务，一个入口", "body": "支持维修、跑腿取送、搬运帮忙、代办代购等合规需求；发布范围以平台实际开放为准。"},
            {"headline": f"需要{service}？先把需求说明白", "body": f"为{audience}提供需求发布入口。预算由发布者自主填写，服务结果以实际完成记录为准。"},
        ],
        "evidence_used": evidence or "无；文案未使用订单、排名或效果数字",
        "safety_check": "已检查平台范围、审核条件和不可核验承诺。",
    }
    return _save("广告文案草稿", payload, output)


def generate_video(payload):
    region, service, keyword, audience, evidence = _context(payload)
    output = {
        "duration": "30秒建议稿",
        "hook": f"在{region}遇到{service}需求，第一步不是急着承诺价格，而是把需求写清楚。",
        "shots": [
            {"seconds": "0-5", "visual": "真实生活场景和问题特写", "voice": f"需要{service}，先说明地点和问题。"},
            {"seconds": "6-15", "visual": "平台需求表单示意，不展示虚构订单", "voice": "填写需求、期望时间和自主预算，等待平台实际开放的服务响应。"},
            {"seconds": "16-24", "visual": "审核与任务状态提示", "voice": "服务和接单能力以账号审核、覆盖区域和任务状态为准。"},
            {"seconds": "25-30", "visual": "品牌与行动提示", "voice": SAFE_POSITIONING + "。"},
        ],
        "caption": f"{region}{service}需求发布参考｜{keyword}",
        "cta": "打开平台，按实际情况填写需求；发布前请核对服务范围。",
        "review_notes": ["只使用自有或已授权画面", "不得伪造用户、订单、前后对比或收益", "人工审核后再发布"],
        "evidence_used": evidence or "无；脚本未写入经营数字",
    }
    return _save("短视频脚本草稿", payload, output)


def history():
    data = read_json("promotion/history.json", {"items": []})
    return {"items": data.get("items", []), "execution": "proposal_only"}
