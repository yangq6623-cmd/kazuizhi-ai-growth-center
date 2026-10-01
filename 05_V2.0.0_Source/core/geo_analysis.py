"""R8-19 GEO Phase 2 deterministic analysis and comparison engine.

Phase 2 converts verified A/B receipts into comparable, traceable metrics.
It never creates evidence, never upgrades C-level data, and never makes a
strategy decision. ChatGPT remains the controller for interpretation and
next-step decisions.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urlsplit

from core.storage import now_iso, read_json, write_json

ANALYSIS_VERSION = "GEO-ANALYSIS-V1-20261001"
ANALYSIS_PATH = "geo_validation/analysis.json"
COMPETITOR_CATALOG_PATH = "geo_validation/competitor_catalog.json"
BRAND = "卡嘴子"
OFFICIAL_DOMAIN = "kazuizhi.com"

_RECOMMEND_POSITIVE = (
    "推荐", "建议", "值得考虑", "可以考虑", "可以选", "可以选择",
    "优先考虑", "比较适合", "更方便", "更合适", "值得看看",
)
_RECOMMEND_NEGATIVE = ("不推荐", "不建议", "不太建议", "不值得", "不要选择")
_NUMBERED_ITEM_RE = re.compile(r"(?:^|\n)\s*(\d{1,2})\s*[\.、\)]\s*([^\n]+)", re.M)
_URL_RE = re.compile(r"https?://[^\s<>'\"\]\)）}，。；;]+", re.I)

_SERVICE_TERMS = {
    "水电安装维修": ("水电", "维修", "安装"),
    "水管漏水维修": ("水管", "漏水", "维修"),
    "管道疏通": ("管道", "疏通", "下水道"),
    "家电维修": ("家电", "维修", "空调", "冰箱", "洗衣机", "热水器", "电视"),
    "安装服务": ("安装", "灯具", "窗帘", "家具"),
    "个人任务": ("个人任务", "小任务", "跑腿", "社区互助"),
    "综合维修": ("维修", "上门", "本地服务"),
    "品牌": (),
}

_DEFAULT_CATALOG = {
    "version": "GEO-COMP-V1-20261001",
    "policy": "仅识别回答中明确出现的候选平台名称；默认不认定为正式竞品，需ChatGPT后续确认。",
    "candidates": [
        {"name": "58同城", "aliases": ["58同城"], "classification": "platform_candidate"},
        {"name": "美团", "aliases": ["美团"], "classification": "platform_candidate"},
        {"name": "大众点评", "aliases": ["大众点评"], "classification": "platform_candidate"},
        {"name": "闲鱼", "aliases": ["闲鱼"], "classification": "platform_candidate"},
        {"name": "百度地图", "aliases": ["百度地图"], "classification": "platform_candidate"},
    ],
}


def _load_catalog():
    value = read_json(COMPETITOR_CATALOG_PATH, {})
    if value and isinstance(value.get("candidates"), list):
        return value
    return _DEFAULT_CATALOG


def _load_snapshot():
    return read_json(ANALYSIS_PATH, {})


def _save_snapshot(value):
    value = dict(value)
    value["updated_at"] = now_iso()
    write_json(ANALYSIS_PATH, value)
    return value


def _sentences(text):
    raw = str(text or "")
    parts = re.split(r"(?<=[。！？!?；;])|\n+", raw)
    return [part.strip() for part in parts if part.strip()]


def _recommendation_signal(answer):
    sentences = _sentences(answer)
    positive_hits = []
    negative_hits = []
    brand_sentences = []
    for index, sentence in enumerate(sentences, 1):
        if BRAND not in sentence and "kazuizhi" not in sentence.lower():
            continue
        brand_sentences.append(index)
        if any(token in sentence for token in _RECOMMEND_NEGATIVE):
            negative_hits.append(sentence)
        for token in _RECOMMEND_POSITIVE:
            if token in sentence:
                positive_hits.append(token)
    if negative_hits and not positive_hits:
        return False, "negative_signal", None, 0.9
    if positive_hits:
        return True, f"explicit:{positive_hits[0]}", (brand_sentences[0] if brand_sentences else None), 0.95
    for match in _NUMBERED_ITEM_RE.finditer(str(answer or "")):
        if BRAND in match.group(2) or "kazuizhi" in match.group(2).lower():
            return True, "numbered_recommendation_item", int(match.group(1)), 0.8
    return False, "no_explicit_recommendation", None, 0.0


def _source_domains(urls):
    domains = []
    for value in urls or []:
        try:
            domain = urlsplit(str(value)).netloc.lower().split("@")[-1].split(":")[0]
        except ValueError:
            domain = ""
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def _candidate_platforms(answer):
    text = str(answer or "")
    found = []
    for item in _load_catalog().get("candidates") or []:
        for alias in item.get("aliases") or []:
            if alias and alias in text:
                found.append({
                    "name": item.get("name") or alias,
                    "classification": item.get("classification") or "platform_candidate",
                    "confirmed_competitor": bool(item.get("confirmed_competitor", False)),
                    "matched_alias": alias,
                })
                break
    unique = {}
    for item in found:
        unique[item["name"]] = item
    return list(unique.values())


def _service_match(receipt, answer):
    service = str(receipt.get("service") or "")
    terms = _SERVICE_TERMS.get(service, ())
    if not terms:
        return True if service == "品牌" else False
    text = str(answer or "")
    return any(term in text for term in terms)


def _score(receipt, mentioned, recommended, cited, service_match):
    kind = str(receipt.get("question_type") or "discovery")
    if kind == "commercial":
        weights = {"mentioned": 25, "recommended": 40, "cited": 20, "service": 15}
    elif kind == "brand":
        weights = {"mentioned": 50, "recommended": 0, "cited": 25, "service": 25}
    else:
        weights = {"mentioned": 45, "recommended": 25, "cited": 20, "service": 10}
    return int(
        (weights["mentioned"] if mentioned else 0)
        + (weights["recommended"] if recommended else 0)
        + (weights["cited"] if cited else 0)
        + (weights["service"] if service_match else 0)
    )


def analyze_receipt(receipt):
    answer = str(receipt.get("raw_answer") or "")
    official = bool(receipt.get("official_truth")) and str(receipt.get("evidence_level") or "") in {"A", "B"}
    extracted = list(receipt.get("extracted_urls") or [])
    cited = list(receipt.get("citation_urls") or [])
    official_urls = [url for url in extracted if OFFICIAL_DOMAIN in str(url).lower()]
    third_party_urls = [url for url in extracted if OFFICIAL_DOMAIN not in str(url).lower()]
    mentioned = BRAND in answer or "kazuizhi" in answer.lower()
    occurrences = answer.count(BRAND) + answer.lower().count("kazuizhi")
    detected_recommended, recommendation_signal, recommendation_position, recommendation_confidence = _recommendation_signal(answer)
    recommended = bool(receipt.get("brand_recommended")) or detected_recommended
    service_match = _service_match(receipt, answer)
    visibility_score = _score(receipt, mentioned, recommended, bool(official_urls), service_match) if official else 0
    candidates = _candidate_platforms(answer)

    gaps = []
    kind = str(receipt.get("question_type") or "discovery")
    if official:
        if not mentioned:
            gaps.append({"code": "brand_visibility_missing", "severity": "high", "label": "回答未出现卡嘴子"})
        if kind == "commercial" and not recommended:
            gaps.append({"code": "recommendation_missing", "severity": "high", "label": "商业推荐题未形成明确推荐"})
        if mentioned and not official_urls:
            gaps.append({"code": "official_citation_missing", "severity": "medium", "label": "提及品牌但未引用官网"})
        if not extracted:
            gaps.append({"code": "source_support_missing", "severity": "medium", "label": "回答没有可追溯来源URL"})
        if kind == "brand" and not service_match:
            gaps.append({"code": "brand_fact_depth_missing", "severity": "medium", "label": "品牌题未覆盖对应能力/服务关键词"})

    return {
        "analysis_version": ANALYSIS_VERSION,
        "official_truth": official,
        "evidence_level": str(receipt.get("evidence_level") or "C"),
        "evidence_id": receipt.get("evidence_id") or receipt.get("receipt_id") or "",
        "question_id": receipt.get("question_id") or "",
        "question_text": receipt.get("question_text") or "",
        "question_type": receipt.get("question_type") or "",
        "service": receipt.get("service") or "",
        "intent": receipt.get("intent") or "",
        "provider": receipt.get("provider") or "",
        "model": receipt.get("model") or "",
        "tested_at": receipt.get("tested_at") or "",
        "brand_mentioned": mentioned,
        "brand_occurrences": occurrences,
        "brand_recommended": recommended,
        "recommendation_signal": recommendation_signal,
        "recommendation_position": recommendation_position,
        "recommendation_confidence": recommendation_confidence,
        "brand_cited": bool(official_urls),
        "official_citation_urls": official_urls,
        "citation_urls": cited,
        "extracted_urls": extracted,
        "source_domains": _source_domains(extracted),
        "source_count": len(extracted),
        "third_party_source_count": len(third_party_urls),
        "service_match": service_match,
        "visibility_score": visibility_score,
        "visibility_state": (
            "recommended" if recommended else "mentioned" if mentioned else "not_visible"
        ) if official else "auxiliary_only",
        "platform_candidates": candidates,
        "gaps": gaps,
    }


def _aggregate(items):
    official = [item for item in items if item.get("official_truth")]
    by_type = {}
    for kind, label in (("discovery", "自然发现"), ("commercial", "商业推荐"), ("brand", "品牌认知")):
        group = [item for item in official if item.get("question_type") == kind]
        tested = len(group)
        mentioned = sum(bool(item.get("brand_mentioned")) for item in group)
        recommended = sum(bool(item.get("brand_recommended")) for item in group)
        cited = sum(bool(item.get("brand_cited")) for item in group)
        scores = [int(item.get("visibility_score") or 0) for item in group]
        by_type[kind] = {
            "label": label,
            "tested": tested,
            "mentioned": mentioned,
            "recommended": recommended,
            "cited": cited,
            "mention_rate": round(mentioned / tested * 100, 1) if tested else None,
            "recommendation_rate": round(recommended / tested * 100, 1) if tested else None,
            "citation_rate": round(cited / tested * 100, 1) if tested else None,
            "avg_visibility_score": round(sum(scores) / tested, 1) if tested else None,
        }

    gap_counter = Counter()
    gap_examples = {}
    for item in official:
        for gap in item.get("gaps") or []:
            code = str(gap.get("code") or "")
            if not code:
                continue
            gap_counter[code] += 1
            gap_examples.setdefault(code, item.get("question_text") or item.get("question_id") or "")
    gaps = []
    severity_rank = {"high": 3, "medium": 2, "low": 1}
    for code, count in gap_counter.most_common():
        example = next(
            (gap for item in official for gap in item.get("gaps") or [] if gap.get("code") == code),
            {},
        )
        gaps.append({
            "code": code,
            "label": example.get("label") or code,
            "severity": example.get("severity") or "medium",
            "count": count,
            "example_question": gap_examples.get(code, ""),
            "priority": severity_rank.get(example.get("severity"), 2) * 100 + count,
        })
    gaps.sort(key=lambda item: (-item["priority"], item["code"]))

    platforms = {}
    for item in official:
        for candidate in item.get("platform_candidates") or []:
            name = candidate.get("name") or ""
            if not name:
                continue
            entry = platforms.setdefault(name, {
                "name": name,
                "classification": candidate.get("classification") or "platform_candidate",
                "confirmed_competitor": bool(candidate.get("confirmed_competitor")),
                "question_count": 0,
                "question_ids": [],
            })
            entry["question_count"] += 1
            if item.get("question_id") and item["question_id"] not in entry["question_ids"]:
                entry["question_ids"].append(item["question_id"])

    return {
        "tested": len(official),
        "mentioned": sum(bool(item.get("brand_mentioned")) for item in official),
        "recommended": sum(bool(item.get("brand_recommended")) for item in official),
        "cited": sum(bool(item.get("brand_cited")) for item in official),
        "mention_rate": round(sum(bool(item.get("brand_mentioned")) for item in official) / len(official) * 100, 1) if official else None,
        "recommendation_rate": round(sum(bool(item.get("brand_recommended")) for item in official) / len(official) * 100, 1) if official else None,
        "citation_rate": round(sum(bool(item.get("brand_cited")) for item in official) / len(official) * 100, 1) if official else None,
        "avg_visibility_score": round(sum(int(item.get("visibility_score") or 0) for item in official) / len(official), 1) if official else None,
        "by_type": by_type,
        "gaps": gaps[:10],
        "platform_candidates": sorted(platforms.values(), key=lambda item: (-item["question_count"], item["name"]))[:20],
    }


def refresh(receipts):
    all_items = [analyze_receipt(item) for item in list(receipts or [])]
    official_items = [item for item in all_items if item.get("official_truth")]
    summary = _aggregate(all_items)
    snapshot = {
        "analysis_version": ANALYSIS_VERSION,
        "controller": "chatgpt",
        "source_policy": "只分析已有A/B Evidence；C级本地辅助不进入正式指标。",
        "generated_at": now_iso(),
        "summary": summary,
        "question_results": official_items,
        "auxiliary_count": len(all_items) - len(official_items),
        "chatgpt_judgement": {
            "status": "pending",
            "required": bool(official_items),
            "reason": "数据分析由确定性规则完成；战略解释、任务优先级和下一步行动仍由ChatGPT总脑决定。",
        },
        "next_stage_reserved": ["gap_to_task", "content_action", "retest"],
    }
    return _save_snapshot(snapshot)


def snapshot():
    value = _load_snapshot()
    if not value:
        return refresh([])
    return value


def analysis_pack():
    value = snapshot()
    return {
        "analysis_version": value.get("analysis_version"),
        "controller": "chatgpt",
        "facts_only": True,
        "summary": value.get("summary") or {},
        "top_gaps": (value.get("summary") or {}).get("gaps") or [],
        "platform_candidates": (value.get("summary") or {}).get("platform_candidates") or [],
        "question_results": value.get("question_results") or [],
        "chatgpt_judgement_required": True,
        "instruction": "只把这些结果作为事实输入；不要把确定性分析直接当成战略决策。",
    }


def status():
    value = snapshot()
    return {
        "analysis_version": value.get("analysis_version"),
        "tested": (value.get("summary") or {}).get("tested", 0),
        "generated_at": value.get("generated_at") or "",
        "ready": bool((value.get("summary") or {}).get("tested", 0)),
        "chatgpt_judgement_status": (value.get("chatgpt_judgement") or {}).get("status", "pending"),
    }
