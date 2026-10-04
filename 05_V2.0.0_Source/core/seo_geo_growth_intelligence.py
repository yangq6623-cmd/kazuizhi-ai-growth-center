"""R8-20 SEO/GEO real-growth intelligence and operating safeguards.

This layer extends the existing truthful SEO/GEO pipeline. It never upgrades an
unverified signal into an external success. Search crawl/index/rank observations
require evidence, GEO formal metrics use A/B Evidence only, and business
attribution stops at order (no revenue/amount/ROI collection).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core import geo_analysis, geo_validation, seo_geo_growth, seo_observability
from core.storage import data_root, now_iso, read_json, write_json

STORE = "r8_20/seo_geo_growth_intelligence.json"
SCHEMA = "kz.seo-geo-growth-intelligence.v1"
BACKUP_DIR = "r8_20/backups"
DYNAMIC_VERSION = "GEO-DYNAMIC-V1-20261002"
ALLOWED_WINDOWS = {7, 30, 90}
MONEY_KEYS = {"amount", "revenue", "income", "profit", "roi", "gmv", "price", "payment", "paid_amount", "成交金额", "收入", "利润"}
ATTRIBUTION_STAGES = {"site_visit", "mini_program_visit", "consultation", "task_published", "order"}
SEARCH_KINDS = {"crawled", "indexed", "ranked", "impressions", "clicks"}

FEATURES = [
    (1, "SEO真实抓取监控", "search_truth"), (2, "SEO真实收录监控", "search_truth"),
    (3, "SEO关键词真实排名", "search_truth"), (4, "搜索曝光量", "search_truth"),
    (5, "搜索点击量", "search_truth"), (6, "CTR点击率", "search_truth"),
    (7, "SEO 7/30/90天趋势", "trend"), (8, "GEO动态问题自动发现", "geo_dynamic"),
    (9, "动态问题去重与版本管理", "geo_dynamic"), (10, "动态问题优先级", "geo_dynamic"),
    (11, "固定50问周期复测", "geo_retest"), (12, "GEO 7天趋势", "trend"),
    (13, "GEO 30天趋势", "trend"), (14, "GEO 90天趋势", "trend"),
    (15, "多AI正式验证自动排程", "multi_ai"), (16, "多AI正式结果矩阵", "multi_ai"),
    (17, "不同AI平台趋势比较", "multi_ai"), (18, "SEO关键词聚类", "governance"),
    (19, "关键词蚕食检测", "governance"), (20, "新建页面或加强旧页决策", "governance"),
    (21, "重复内容合并建议", "governance"), (22, "自动内链推荐与安全执行", "governance"),
    (23, "孤儿页修复", "governance"), (24, "老页面内容衰减监控", "governance"),
    (25, "老页面自动刷新任务", "governance"), (26, "SEO/GEO来源追踪ID", "attribution"),
    (27, "官网访问到小程序归因", "attribution"), (28, "小程序到咨询归因", "attribution"),
    (29, "咨询到任务发布归因", "attribution"), (30, "任务到订单归因", "attribution"),
    (31, "ChatGPT按业务转化调优先级", "controller"), (32, "有流量无咨询订单内容自动降优先级", "controller"),
    (33, "技术SEO深度检查", "technical"), (34, "GEO第三方可信来源与引用缺口", "geo_source"),
    (35, "连接器健康监控", "safeguard"), (36, "失败重试限流熔断死信", "safeguard"),
    (37, "SEO/GEO历史数据备份恢复", "safeguard"), (38, "调用额度与异常循环保护", "safeguard"),
]

DEFAULT = {
    "schema": SCHEMA,
    "policy": {
        "fixed50_schedule_enabled": False,
        "dynamic_geo_enabled": True,
        "daily_external_call_budget": 120,
        "connector_failure_threshold": 3,
        "content_decay_days": 45,
        "traffic_without_conversion_threshold": 50,
        "auto_internal_link_staging": True,
        "auto_refresh_jobs": True,
        "money_metrics_disabled": True,
    },
    "search_observations": [],
    "dynamic_questions": [],
    "dynamic_versions": [],
    "trend_snapshots": [],
    "attribution_events": [],
    "technical_vitals": [],
    "connector_health": {},
    "dead_letters": [],
    "daily_budgets": {},
    "refresh_queue": [],
    "controller_actions": [],
    "audit": [],
    "last_run_at": "",
    "updated_at": "",
}


def _load():
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    for key, value in DEFAULT.items():
        data.setdefault(key, deepcopy(value))
    for key, value in DEFAULT["policy"].items():
        data["policy"].setdefault(key, value)
    return data


def _save(data):
    data = dict(data)
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["search_observations"] = list(data.get("search_observations") or [])[-5000:]
    data["dynamic_questions"] = list(data.get("dynamic_questions") or [])[-500:]
    data["trend_snapshots"] = list(data.get("trend_snapshots") or [])[-400:]
    data["attribution_events"] = list(data.get("attribution_events") or [])[-10000:]
    data["technical_vitals"] = list(data.get("technical_vitals") or [])[-500:]
    data["dead_letters"] = list(data.get("dead_letters") or [])[-500:]
    data["audit"] = list(data.get("audit") or [])[-1000:]
    write_json(STORE, data)
    return data


def _id(prefix, *parts):
    raw = "|".join(str(x or "") for x in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:14].upper()}"


def _audit(data, kind, detail=None):
    data.setdefault("audit", []).append({"at": now_iso(), "kind": kind, "detail": deepcopy(detail or {})})


def _reject_money(value, path="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).strip().lower()
            if lower in MONEY_KEYS or any(token in lower for token in ("revenue", "profit", "roi", "paid_amount", "payment_amount")):
                raise ValueError(f"SEO/GEO归因不采集金额/收入/ROI字段：{path}.{key}")
            _reject_money(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_money(item, f"{path}[{index}]")


def _evidence(payload):
    value = payload.get("evidence") or payload.get("receipt") or payload.get("source_ref")
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "").strip()


def feature_registry():
    return [{"id": number, "name": name, "group": group, "code_state": "implemented"} for number, name, group in FEATURES]


def source_tracking_id(asset_or_key):
    if isinstance(asset_or_key, dict):
        key = asset_or_key.get("id") or asset_or_key.get("opportunity_id") or asset_or_key.get("keyword")
    else:
        key = asset_or_key
    return _id("KZSRC", key or "unknown")


def record_search_observation(payload):
    """Record observable search truth and update the canonical SEO asset stage when applicable."""
    payload = dict(payload or {})
    _reject_money(payload)
    kind = str(payload.get("kind") or "").strip().lower()
    if kind not in SEARCH_KINDS:
        raise ValueError("kind 必须是 crawled/indexed/ranked/impressions/clicks")
    asset_id = str(payload.get("asset_id") or "").strip()
    url = str(payload.get("url") or "").strip()
    engine = str(payload.get("engine") or "").strip()
    evidence = _evidence(payload)
    if not engine or not evidence:
        raise ValueError("搜索观察必须提供 engine 和真实 evidence")
    if not asset_id and not url:
        raise ValueError("搜索观察必须关联 asset_id 或 url")
    value = payload.get("value")
    rank = payload.get("rank")
    if kind == "ranked":
        rank = int(rank or value or 0)
        if rank <= 0:
            raise ValueError("真实排名必须是正整数")
        value = rank
    elif kind in {"impressions", "clicks"}:
        value = int(value or 0)
        if value < 0:
            raise ValueError("曝光/点击不能为负数")
    row = {
        "id": _id("SEOOBS", kind, asset_id, url, engine, now_iso(), len(_load().get("search_observations") or [])),
        "observed_at": str(payload.get("observed_at") or now_iso()),
        "kind": kind, "asset_id": asset_id, "url": url, "engine": engine,
        "keyword": str(payload.get("keyword") or ""), "value": value,
        "evidence": evidence[:4000], "source": str(payload.get("source") or "external_verified")[:120],
    }
    data = _load()
    data["search_observations"].append(row)
    _audit(data, "search_observation", {"kind": kind, "asset_id": asset_id, "engine": engine})
    _save(data)
    if asset_id and kind in {"crawled", "indexed", "ranked"}:
        stage = kind.upper()
        stage_payload = {}
        if kind == "crawled": stage_payload["crawl_evidence"] = evidence
        if kind == "indexed": stage_payload["index_evidence"] = evidence
        if kind == "ranked": stage_payload.update({"rank": int(value), "engine": engine, "keyword": row["keyword"]})
        try:
            seo_geo_growth.record_asset_stage(asset_id, stage, stage_payload)
        except ValueError as error:
            # Preserve the observation even if an older pipeline stage has not yet been truthfully reached.
            data = _load(); _audit(data, "search_stage_deferred", {"asset_id": asset_id, "stage": stage, "reason": str(error)}); _save(data)
    return row


def _search_rollup(days=30):
    days = int(days if int(days) in ALLOWED_WINDOWS else 30)
    cutoff = datetime.now().astimezone() - timedelta(days=days - 1)
    rows = []
    for item in _load().get("search_observations") or []:
        try: stamp = datetime.fromisoformat(str(item.get("observed_at") or ""))
        except ValueError: continue
        if stamp >= cutoff:
            rows.append(item)
    latest_truth = {}
    time_totals = defaultdict(lambda: {"impressions": 0, "clicks": 0})
    for item in rows:
        key = (item.get("asset_id") or item.get("url"), item.get("engine"), item.get("kind"), item.get("keyword") or "")
        if item.get("kind") in {"crawled", "indexed", "ranked"}:
            if key not in latest_truth or str(item.get("observed_at")) > str(latest_truth[key].get("observed_at")):
                latest_truth[key] = item
        if item.get("kind") in {"impressions", "clicks"}:
            date = str(item.get("observed_at") or "")[:10]
            time_totals[date][item["kind"]] += int(item.get("value") or 0)
    impressions = sum(v["impressions"] for v in time_totals.values())
    clicks = sum(v["clicks"] for v in time_totals.values())
    return {
        "window_days": days,
        "crawled": sum(1 for x in latest_truth.values() if x.get("kind") == "crawled"),
        "indexed": sum(1 for x in latest_truth.values() if x.get("kind") == "indexed"),
        "ranked": sum(1 for x in latest_truth.values() if x.get("kind") == "ranked"),
        "impressions": impressions, "clicks": clicks,
        "ctr": round(clicks * 100 / impressions, 2) if impressions else None,
        "daily": [{"date": date, **values, "ctr": round(values["clicks"] * 100 / values["impressions"], 2) if values["impressions"] else None} for date, values in sorted(time_totals.items())],
    }


def _normalize_question(text):
    return re.sub(r"[\s，。？！、,.!?;；:：]+", "", str(text or "").casefold())


def discover_dynamic_questions(candidates, source="controller", evidence=""):
    """Add deduplicated dynamic GEO questions. Discovery may be model-assisted; formal results remain A/B gated."""
    if not isinstance(candidates, list):
        raise ValueError("candidates 必须是列表")
    data = _load()
    existing = {_normalize_question(q.get("question_text")): q for q in (geo_validation.question_set().get("questions") or [])}
    existing.update({_normalize_question(q.get("question_text")): q for q in data.get("dynamic_questions") or []})
    added = []
    for raw in candidates[:100]:
        row = {"question_text": raw} if isinstance(raw, str) else dict(raw or {})
        text = str(row.get("question_text") or row.get("question") or "").strip()
        norm = _normalize_question(text)
        if len(text) < 5 or not norm or norm in existing:
            continue
        service = str(row.get("service") or "综合维修")[:60]
        intent = str(row.get("intent") or "dynamic_discovery")[:60]
        region = str(row.get("region") or "涟水县")[:60]
        priority = int(row.get("priority") or (90 if any(token in text for token in ("推荐", "哪个", "哪里", "急", "马上")) else 60))
        priority = max(1, min(priority, 100))
        item = {
            "question_id": _id("GEODYN", DYNAMIC_VERSION, norm), "version": DYNAMIC_VERSION,
            "question_text": text[:300], "region": region, "service": service, "intent": intent,
            "priority": priority, "source": str(row.get("source") or source)[:120],
            "source_evidence": str(row.get("evidence") or evidence)[:1000], "state": "active",
            "created_at": now_iso(), "last_scheduled_at": "",
        }
        data["dynamic_questions"].append(item); existing[norm] = item; added.append(item)
    if added:
        version = {"version": DYNAMIC_VERSION, "at": now_iso(), "added": len(added), "total": len(data["dynamic_questions"])}
        data["dynamic_versions"].append(version); _audit(data, "dynamic_geo_questions_added", version)
    _save(data)
    return {"added": added, "total": len(data["dynamic_questions"]), "version": DYNAMIC_VERSION}


def dynamic_questions(limit=200):
    rows = [x for x in _load().get("dynamic_questions") or [] if x.get("state") == "active"]
    rows.sort(key=lambda x: (-int(x.get("priority") or 0), str(x.get("created_at") or "")))
    return rows[:max(1, min(int(limit or 200), 500))]


def schedule_multi_provider_validation(providers, limit=3, include_dynamic=True):
    providers = [str(x).strip() for x in (providers or []) if str(x).strip()]
    if not providers:
        raise ValueError("至少提供一个真实外部AI provider")
    limit = max(1, min(int(limit or 3), 50))
    fixed = [x.get("question_id") for x in geo_validation.question_set().get("questions") or []][:limit]
    tasks = []
    for provider in providers[:8]:
        result = geo_validation.create_and_enqueue_plan(limit=len(fixed), provider=provider, test_method="browser", question_ids=fixed)
        tasks.extend(result.get("tasks") or [])
    # Dynamic questions are maintained separately because the immutable GEO50 validator only accepts fixed IDs.
    dynamic = dynamic_questions(limit) if include_dynamic else []
    data = _load()
    for row in dynamic:
        row["last_scheduled_at"] = now_iso()
    _audit(data, "multi_provider_validation_scheduled", {"providers": providers[:8], "fixed_tasks": len(tasks), "dynamic_candidates": len(dynamic)})
    _save(data)
    return {"providers": providers[:8], "fixed_tasks": tasks, "dynamic_candidates": dynamic, "truth": "只有后续取得真实A/B Evidence的结果进入正式GEO矩阵"}


def configure_fixed50_schedule(enabled):
    data = _load(); data["policy"]["fixed50_schedule_enabled"] = bool(enabled)
    _audit(data, "fixed50_schedule_config", {"enabled": bool(enabled)}); _save(data)
    return deepcopy(data["policy"])


def schedule_fixed50_retest(provider="browser_external_ai", limit=50):
    data = _load()
    if not data["policy"].get("fixed50_schedule_enabled"):
        return {"skipped": True, "reason": "field_acceptance_gate", "truth": "完成1→3→10→50实机放量后再开启周期复测"}
    ids = [x.get("question_id") for x in geo_validation.question_set().get("questions") or []][:max(1, min(int(limit or 50), 50))]
    result = geo_validation.create_and_enqueue_plan(limit=len(ids), provider=str(provider or "browser_external_ai"), test_method="browser", question_ids=ids)
    _audit(data, "fixed50_retest_scheduled", {"provider": provider, "tasks": len(result.get("tasks") or [])}); _save(data)
    return result


def provider_matrix():
    snapshot = geo_analysis.snapshot()
    if int((snapshot.get("summary") or {}).get("tested") or 0) != int((geo_validation.dashboard().get("official") or {}).get("tested") or 0):
        snapshot = geo_analysis.refresh(geo_validation.receipts(1000))
    return {
        "formal_evidence": int((snapshot.get("summary") or {}).get("tested") or 0),
        "providers": deepcopy(snapshot.get("provider_comparison") or []),
        "truth": "仅统计最新正式A/B Evidence；C级辅助结果不进入矩阵",
    }


def _tokenize_keyword(value):
    text = str(value or "").lower()
    tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text)
    expanded = []
    for token in tokens:
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 4:
            expanded.extend([token, token[:2], token[-2:]])
        else:
            expanded.append(token)
    return set(expanded)


def keyword_governance():
    snap = seo_geo_growth.dashboard()
    opportunities = list(snap.get("opportunities") or [])
    assets = list(snap.get("assets") or [])
    asset_by_opp = {str(x.get("opportunity_id") or ""): x for x in assets}
    groups = defaultdict(list)
    for opp in opportunities:
        key = f"{opp.get('region') or '未知'}｜{opp.get('service') or '综合'}"
        groups[key].append(opp)
    clusters = []
    cannibalization = []
    decisions = []
    duplicates = []
    for key, rows in groups.items():
        cluster_id = _id("KWCL", key)
        clusters.append({"cluster_id": cluster_id, "label": key, "keywords": [x.get("keyword") for x in rows], "count": len(rows)})
        for i, left in enumerate(rows):
            lt = _tokenize_keyword(left.get("keyword"))
            best = None
            for right in rows[i+1:]:
                rt = _tokenize_keyword(right.get("keyword")); union = lt | rt
                score = len(lt & rt) / len(union) if union else 0
                if score >= 0.45:
                    pair = {"cluster_id": cluster_id, "keyword_a": left.get("keyword"), "keyword_b": right.get("keyword"), "similarity": round(score, 2)}
                    cannibalization.append(pair)
                    if score >= 0.7: duplicates.append({**pair, "recommendation": "优先合并/加强主页面，避免重复新建"})
                    if best is None or score > best[0]: best = (score, right)
            asset = asset_by_opp.get(str(left.get("id") or ""))
            decision = "strengthen_existing" if asset or best else "new_page"
            decisions.append({"opportunity_id": left.get("id"), "keyword": left.get("keyword"), "decision": decision, "existing_asset_id": (asset or {}).get("id") or "", "reason": "已有页面或同簇高相似关键词" if decision == "strengthen_existing" else "同簇暂无可复用页面"})
    return {"clusters": clusters, "cannibalization": cannibalization[:100], "page_decisions": decisions, "duplicate_merge_suggestions": duplicates[:100]}


def internal_link_plan():
    snap = seo_geo_growth.dashboard(); assets = list(snap.get("assets") or [])
    groups = defaultdict(list)
    for asset in assets:
        if asset.get("canonical"):
            groups[(asset.get("region"), asset.get("service"))].append(asset)
    recommendations = []
    for rows in groups.values():
        for source in rows:
            targets = [x for x in rows if x.get("id") != source.get("id") and x.get("canonical")][:3]
            for target in targets:
                recommendations.append({"source_asset_id": source.get("id"), "target_asset_id": target.get("id"), "target_url": target.get("canonical"), "anchor": target.get("keyword") or target.get("service"), "safe_scope": "staging_only"})
    observation = seo_observability.status(); orphan = int((observation.get("links") or {}).get("orphan_candidates") or 0)
    return {"recommendations": recommendations[:200], "observed_orphan_candidates": orphan}


def apply_internal_links(limit=20):
    data = _load()
    if not data["policy"].get("auto_internal_link_staging"):
        return {"skipped": True, "reason": "policy_disabled"}
    snap = seo_geo_growth.dashboard(); assets = {str(x.get("id")): x for x in snap.get("assets") or []}
    changed = []
    for rec in internal_link_plan()["recommendations"]:
        if len(changed) >= int(limit): break
        source = assets.get(str(rec["source_asset_id"])); path = Path(str((source or {}).get("staging_path") or ""))
        if not path.is_file(): continue
        try: text = path.read_text(encoding="utf-8")
        except OSError: continue
        marker = f'data-kz-related="{rec["target_asset_id"]}"'
        if marker in text: continue
        block = f'<p {marker}>相关推荐：<a href="{rec["target_url"]}">{rec["anchor"]}</a></p>'
        if "</main>" not in text: continue
        text = text.replace("</main>", block + "</main>", 1)
        path.write_text(text, encoding="utf-8"); changed.append(rec)
    if changed: _audit(data, "staging_internal_links_applied", {"count": len(changed)}); _save(data)
    return {"changed": changed, "count": len(changed), "truth": "只修改本地staging；不会冒充公网已发布"}


def content_decay():
    snap = seo_geo_growth.dashboard(); now = datetime.now().astimezone(); threshold = int(_load()["policy"].get("content_decay_days") or 45)
    search = _search_rollup(90); traffic_by_asset = Counter()
    for row in _load().get("search_observations") or []:
        if row.get("kind") in {"impressions", "clicks"}: traffic_by_asset[str(row.get("asset_id") or "")] += int(row.get("value") or 0)
    rows = []
    for asset in snap.get("assets") or []:
        stamp = asset.get("published_at") or asset.get("generated_at") or asset.get("created_at")
        try: age = (now - datetime.fromisoformat(str(stamp))).days
        except (ValueError, TypeError): age = 0
        if age >= threshold:
            rows.append({"asset_id": asset.get("id"), "keyword": asset.get("keyword"), "age_days": age, "traffic_signal": traffic_by_asset[str(asset.get("id") or "")], "recommendation": "refresh"})
    return {"threshold_days": threshold, "candidates": rows, "search_window": search["window_days"]}


def queue_refresh_jobs(limit=10):
    data = _load(); candidates = content_decay()["candidates"][:max(1, min(int(limit or 10), 20))]
    existing = {str(x.get("asset_id")) for x in data.get("refresh_queue") or [] if x.get("state") in {"queued", "done"}}
    added = []
    for item in candidates:
        if str(item.get("asset_id")) in existing: continue
        row = {**item, "refresh_id": _id("SEOREF", item.get("asset_id"), now_iso()[:10]), "state": "queued", "created_at": now_iso()}
        data["refresh_queue"].append(row); added.append(row)
    if added: _audit(data, "content_refresh_queued", {"count": len(added)}); _save(data)
    return {"added": added, "count": len(added)}


def record_attribution(payload):
    payload = dict(payload or {}); _reject_money(payload)
    stage = str(payload.get("stage") or "").strip().lower()
    if stage not in ATTRIBUTION_STAGES: raise ValueError("归因stage必须到 site_visit/mini_program_visit/consultation/task_published/order 之一")
    source_id = str(payload.get("source_tracking_id") or "").strip()
    if not source_id: raise ValueError("归因必须包含 source_tracking_id")
    evidence = _evidence(payload)
    if stage in {"consultation", "task_published", "order"} and not evidence:
        raise ValueError("咨询/任务/订单归因必须有真实 evidence")
    row = {
        "event_id": _id("ATTR", source_id, stage, payload.get("lead_id"), payload.get("task_id"), payload.get("order_id"), now_iso()),
        "at": str(payload.get("at") or now_iso()), "source_tracking_id": source_id,
        "channel": str(payload.get("channel") or "seo_geo")[:40], "stage": stage,
        "asset_id": str(payload.get("asset_id") or ""), "question_id": str(payload.get("question_id") or ""),
        "lead_id": str(payload.get("lead_id") or ""), "task_id": str(payload.get("task_id") or ""), "order_id": str(payload.get("order_id") or ""),
        "evidence": evidence[:2000],
    }
    if stage == "order" and not row["order_id"]: raise ValueError("订单归因必须提供 order_id")
    data = _load(); data["attribution_events"].append(row); _audit(data, "attribution", {"stage": stage, "source_tracking_id": source_id}); _save(data)
    if row["asset_id"] and stage == "order":
        try: seo_geo_growth.record_asset_stage(row["asset_id"], "CONVERTED", {"order_id": row["order_id"]})
        except ValueError: pass
    return row


def attribution_funnel(days=30):
    days = int(days if int(days) in ALLOWED_WINDOWS else 30); cutoff = datetime.now().astimezone() - timedelta(days=days-1)
    counts = Counter(); sources = defaultdict(Counter)
    for row in _load().get("attribution_events") or []:
        try: stamp = datetime.fromisoformat(str(row.get("at") or ""))
        except ValueError: continue
        if stamp < cutoff: continue
        counts[row.get("stage")] += 1; sources[str(row.get("source_tracking_id") or "")][row.get("stage")] += 1
    return {"window_days": days, "site_visit": counts["site_visit"], "mini_program_visit": counts["mini_program_visit"], "consultation": counts["consultation"], "task_published": counts["task_published"], "order": counts["order"], "by_source": {k: dict(v) for k,v in sources.items()}}


def controller_priorities():
    governance = keyword_governance(); funnel = attribution_funnel(90); data = _load(); threshold = int(data["policy"].get("traffic_without_conversion_threshold") or 50)
    traffic = Counter()
    for row in data.get("search_observations") or []:
        if row.get("kind") in {"clicks", "impressions"}: traffic[str(row.get("asset_id") or "")] += int(row.get("value") or 0)
    by_source = funnel.get("by_source") or {}; snap = seo_geo_growth.dashboard(); rows = []
    for asset in snap.get("assets") or []:
        sid = source_tracking_id(asset); conv = by_source.get(sid, {}); t = traffic[str(asset.get("id") or "")]
        order_count = int(conv.get("order") or 0); consultation = int(conv.get("consultation") or 0); task_count = int(conv.get("task_published") or 0)
        if order_count or task_count: action, priority = "amplify", 100
        elif consultation: action, priority = "strengthen", 85
        elif t >= threshold: action, priority = "deprioritize", 25
        else: action, priority = "observe", 60
        rows.append({"asset_id": asset.get("id"), "source_tracking_id": sid, "keyword": asset.get("keyword"), "traffic_signal": t, "consultations": consultation, "tasks": task_count, "orders": order_count, "controller_action": action, "priority_score": priority})
    rows.sort(key=lambda x: (-x["priority_score"], -x["orders"], -x["tasks"], -x["consultations"]))
    return {"actions": rows, "governance": governance, "truth": "优先级只依据真实搜索/咨询/任务/订单信号，不使用成交金额或ROI"}


def ingest_web_vitals(payload):
    payload = dict(payload or {}); _reject_money(payload)
    source = str(payload.get("source") or "").strip(); evidence = _evidence(payload)
    if not source or not evidence: raise ValueError("CWV/Lighthouse指标必须提供真实 source 与 evidence")
    metrics = {}
    for key in ("lcp_ms", "inp_ms", "cls", "fcp_ms", "ttfb_ms"):
        if payload.get(key) is not None:
            value = float(payload[key]);
            if value < 0: raise ValueError("Web Vitals指标不能为负数")
            metrics[key] = value
    if not metrics: raise ValueError("至少提供一个真实Web Vitals指标")
    row = {"at": str(payload.get("at") or now_iso()), "url": str(payload.get("url") or ""), "source": source[:120], "evidence": evidence[:2000], "metrics": metrics}
    data = _load(); data["technical_vitals"].append(row); _audit(data, "web_vitals_ingested", {"url": row["url"], "source": source}); _save(data); return row


def technical_seo_status():
    obs = seo_observability.status(); snap = seo_geo_growth.dashboard(); latest_vitals = (_load().get("technical_vitals") or [])[-1:] 
    problems = []
    for page in obs.get("pages") or []:
        status = int(page.get("status") or 0)
        if status == 404: problems.append({"type":"404", "url":page.get("url"), "severity":"high"})
        elif 300 <= status < 400: problems.append({"type":"redirect", "url":page.get("url"), "severity":"medium"})
        elif status == 0 or status >= 500: problems.append({"type":"unreachable", "url":page.get("url"), "severity":"high"})
    links = obs.get("links") or {}
    if int(links.get("pages_without_outbound_internal_links") or 0) > 0: problems.append({"type":"weak_internal_links", "count":links.get("pages_without_outbound_internal_links"), "severity":"medium"})
    if int(links.get("orphan_candidates") or 0) > 0: problems.append({"type":"orphan_candidates", "count":links.get("orphan_candidates"), "severity":"medium"})
    staging = (snap.get("technical") or {}).get("staging") or {}
    for name in ("robots_generated", "sitemap_generated"):
        if not staging.get(name): problems.append({"type":name.replace("_generated", "_missing"), "severity":"high"})
    return {"public_observation": obs, "latest_web_vitals": latest_vitals[0] if latest_vitals else None, "web_vitals_state": "measured" if latest_vitals else "waiting_real_provider", "problems": problems, "truth": "HTTP/内链来自真实公网观察；CWV仅在导入真实测量证据后显示"}


def third_party_source_gaps():
    snap = geo_analysis.snapshot()
    if not snap: snap = geo_analysis.refresh(geo_validation.receipts(1000))
    domains = [x for x in snap.get("source_domains") or [] if not x.get("official_domain")]
    official_domain_seen = any(x.get("official_domain") for x in snap.get("source_domains") or [])
    actions = []
    for row in domains[:20]:
        actions.append({"domain": row.get("domain"), "question_count": row.get("question_count"), "action": "研究该真实来源为何被AI引用；仅通过合法公开资料/合作/资料完善增加可信可引用信息", "auto_post": False})
    if not official_domain_seen:
        actions.insert(0, {"domain":"kazuizhi.com", "action":"优先完善官网事实页、FAQ、服务区域和可引用结构", "auto_post":False})
    return {"observed_third_party_domains": domains[:30], "actions": actions[:30], "truth": "不自动批量发垃圾外链/论坛；只依据真实引用来源生成合规建设任务"}


def record_connector_health(name, ok, detail=""):
    name = str(name or "").strip()
    if not name: raise ValueError("connector name不能为空")
    data = _load(); row = dict((data.get("connector_health") or {}).get(name) or {})
    failures = 0 if ok else int(row.get("consecutive_failures") or 0) + 1
    threshold = int(data["policy"].get("connector_failure_threshold") or 3)
    row.update({"name": name, "ok": bool(ok), "checked_at": now_iso(), "detail": str(detail)[:1000], "consecutive_failures": failures, "breaker_open": failures >= threshold})
    data["connector_health"][name] = row
    if row["breaker_open"]: data["dead_letters"].append({"at":now_iso(), "kind":"connector_breaker", "connector":name, "detail":row["detail"]})
    _audit(data, "connector_health", {"name":name, "ok":bool(ok), "failures":failures}); _save(data); return row


def consume_budget(bucket="external", units=1):
    units = max(1, int(units or 1)); data = _load(); day = now_iso()[:10]
    daily = data["daily_budgets"].setdefault(day, {}); used = int(daily.get(bucket) or 0); limit = int(data["policy"].get("daily_external_call_budget") or 120)
    if used + units > limit:
        data["dead_letters"].append({"at":now_iso(), "kind":"budget_block", "bucket":bucket, "requested":units, "used":used, "limit":limit}); _save(data)
        return {"allowed":False, "used":used, "limit":limit, "reason":"daily_budget_exceeded"}
    daily[bucket] = used + units; _save(data); return {"allowed":True, "used":daily[bucket], "limit":limit}


def register_failure(kind, payload, error, retry_count=0, max_retries=2):
    data = _load(); retry_count = int(retry_count or 0)
    row = {"at":now_iso(), "kind":str(kind), "payload":deepcopy(payload or {}), "error":str(error)[:1000], "retry_count":retry_count, "state":"retry" if retry_count < int(max_retries) else "dead_letter"}
    if row["state"] == "dead_letter": data["dead_letters"].append(row)
    _audit(data, "operation_failure", {"kind":kind, "state":row["state"], "retry_count":retry_count}); _save(data); return row


def create_backup(label="manual"):
    root = data_root(); stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S"); backup_id = f"{stamp}_{re.sub(r'[^a-zA-Z0-9_-]+','-',str(label))[:30]}"
    folder = root / BACKUP_DIR / backup_id; folder.mkdir(parents=True, exist_ok=True)
    targets = [STORE, "geo_validation/receipts.json", "geo_validation/analysis.json", "geo_validation/question_set.json", "geo_validation/phase3.json", "r8_13/seo_geo_growth.json"]
    copied = []
    for rel in targets:
        source = root / rel
        if not source.is_file(): continue
        dest = folder / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest); copied.append(rel)
    manifest = {"backup_id":backup_id, "created_at":now_iso(), "files":copied, "truth":"仅备份SEO/GEO状态与证据JSON，不包含密钥或个人数据"}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def restore_backup(backup_id, confirm=False):
    if confirm is not True: raise PermissionError("恢复历史数据需要 confirm=true")
    root = data_root(); folder = root / BACKUP_DIR / str(backup_id)
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file(): raise ValueError("备份不存在")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")); restored = []
    for rel in manifest.get("files") or []:
        source = folder / rel
        if not source.is_file(): continue
        dest = root / rel; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, dest); restored.append(rel)
    return {"backup_id":backup_id, "restored":restored, "restored_at":now_iso()}


def capture_trend_snapshot(force=False):
    data = _load(); today = now_iso()[:10]
    existing = next((x for x in data.get("trend_snapshots") or [] if x.get("date") == today), None)
    if existing and not force: return existing
    seo = seo_geo_growth.dashboard(); formal = geo_analysis.snapshot()
    if int((formal.get("summary") or {}).get("tested") or 0) != int((geo_validation.dashboard().get("official") or {}).get("tested") or 0): formal = geo_analysis.refresh(geo_validation.receipts(1000))
    summary = formal.get("summary") or {}; search = _search_rollup(7); funnel = attribution_funnel(7)
    row = {
        "date": today, "captured_at": now_iso(),
        "seo": {"published": int((seo.get("summary") or {}).get("public_pages") or 0), "submitted": int((seo.get("summary") or {}).get("submitted_urls") or 0), "crawled": int((seo.get("summary") or {}).get("crawled_urls") or search["crawled"] or 0), "indexed": int((seo.get("summary") or {}).get("indexed_urls") or search["indexed"] or 0), "ranked": int((seo.get("summary") or {}).get("ranked_urls") or search["ranked"] or 0), "impressions": search["impressions"], "clicks": search["clicks"], "ctr": search["ctr"]},
        "geo": {"tested": int(summary.get("tested") or 0), "mention_rate": summary.get("mention_rate"), "recommendation_rate": summary.get("recommendation_rate"), "citation_rate": summary.get("citation_rate"), "avg_visibility_score": summary.get("avg_visibility_score")},
        "business": {k:funnel.get(k,0) for k in ("site_visit","mini_program_visit","consultation","task_published","order")},
        "provider_matrix": provider_matrix().get("providers") or [],
    }
    data["trend_snapshots"] = [x for x in data.get("trend_snapshots") or [] if x.get("date") != today] + [row]; _save(data); return row


def trends(days=30):
    days = int(days); days = days if days in ALLOWED_WINDOWS else 30; capture_trend_snapshot(force=False)
    cutoff = (datetime.now().astimezone().date() - timedelta(days=days-1)).isoformat()
    rows = [x for x in _load().get("trend_snapshots") or [] if str(x.get("date") or "") >= cutoff]
    rows.sort(key=lambda x: x.get("date") or "")
    return {"window_days":days, "points":rows, "seo":[{"date":x["date"], **x.get("seo",{})} for x in rows], "geo":[{"date":x["date"], **x.get("geo",{})} for x in rows], "business":[{"date":x["date"], **x.get("business",{})} for x in rows]}


def alerts(days=30, trend=None, priorities=None):
    """Return actionable alerts without rebuilding an already assembled snapshot.

    The owner cockpit asks for a complete SEO/GEO status while the detailed
    workspace is also loading.  Recomputing the trend and controller plan
    three times on that path caused cold-start requests to exceed the browser
    timeout.  Callers that already have those values can pass them here.
    """
    items = []; trend = (trend or trends(days)).get("points") or []; health = _load().get("connector_health") or {}
    for name,row in health.items():
        if row.get("breaker_open") or not row.get("ok", True): items.append({"severity":"high" if row.get("breaker_open") else "medium", "kind":"connector", "title":f"{name}连接器异常", "detail":row.get("detail") or "连续失败"})
    if len(trend) >= 2:
        first, last = trend[0], trend[-1]
        for key,label in (("mention_rate","GEO提及率"),("recommendation_rate","GEO推荐率"),("citation_rate","官网引用率")):
            a=(first.get("geo") or {}).get(key); b=(last.get("geo") or {}).get(key)
            if a is not None and b is not None and float(b) < float(a): items.append({"severity":"medium", "kind":"geo_drop", "title":f"{label}下降", "detail":f"{a}% → {b}%"})
    for row in (priorities if priorities is not None else controller_priorities().get("actions") or []):
        if row.get("controller_action") == "deprioritize": items.append({"severity":"low", "kind":"low_conversion", "title":"有流量但无业务动作", "detail":row.get("keyword") or row.get("asset_id")})
    return items[:30]


def controller_brief(days=30, trend=None, priorities=None, issues=None):
    trend = trend or trends(days)
    priorities = priorities if priorities is not None else controller_priorities().get("actions") or []
    issues = issues if issues is not None else alerts(days, trend=trend, priorities=priorities)
    top = [x for x in priorities if x.get("controller_action") in {"amplify","strengthen"}][:3]; low=[x for x in priorities if x.get("controller_action")=="deprioritize"][:3]
    return {
        "controller":"chatgpt", "window_days":trend["window_days"],
        "summary": f"当前有 {len(top)} 个建议放大/加强项、{len(low)} 个建议降优先级项、{len(issues)} 条异常提醒。",
        "amplify": top, "deprioritize": low, "alerts": issues[:10],
        "instruction":"ChatGPT总脑应结合真实排名、GEO A/B Evidence以及咨询/任务/订单信号决定下一轮；豆包负责执行辅助，不替代总脑授权。",
    }


def run_once(force=False):
    data = _load(); budget = consume_budget("r8_20_tick", 1)
    if not budget.get("allowed"):
        return {"skipped":True, "reason":budget.get("reason"), "status":status(30)}
    capture_trend_snapshot(force=bool(force)); internal = apply_internal_links(limit=20) if data["policy"].get("auto_internal_link_staging") else {"skipped":True}; refresh = queue_refresh_jobs(limit=10) if data["policy"].get("auto_refresh_jobs") else {"skipped":True}
    data = _load(); data["last_run_at"] = now_iso(); _audit(data,"r8_20_tick",{"internal_links":internal.get("count",0),"refresh":refresh.get("count",0)}); _save(data)
    return {"skipped":False,"internal_links":internal,"refresh":refresh,"status":status(30)}


def status(days=30):
    days = int(days); days = days if days in ALLOWED_WINDOWS else 30
    data = _load(); snap = seo_geo_growth.dashboard(); formal = geo_analysis.snapshot()
    if int((formal.get("summary") or {}).get("tested") or 0) != int((geo_validation.dashboard().get("official") or {}).get("tested") or 0): formal = geo_analysis.refresh(geo_validation.receipts(1000))
    # Assemble expensive, read-only views once.  This endpoint is requested by
    # both the cockpit and the dedicated workspace at cold start, so repeated
    # trend/controller calculations make the UI look like it is redirecting or
    # stalled even when the local service is healthy.
    trend = trends(days)
    priorities = controller_priorities().get("actions") or []
    issues = alerts(days, trend=trend, priorities=priorities)
    controller = controller_brief(days, trend=trend, priorities=priorities, issues=issues)
    return {
        "schema":SCHEMA, "completion_target":"90-95% autonomous SEO/GEO operating loop", "features":feature_registry(), "feature_count":len(FEATURES),
        "policy":deepcopy(data["policy"]), "seo_summary":deepcopy(snap.get("summary") or {}), "search":_search_rollup(days),
        "geo_summary":deepcopy(formal.get("summary") or {}), "provider_matrix":provider_matrix(), "dynamic_geo":{"version":DYNAMIC_VERSION,"questions":dynamic_questions(100),"count":len(dynamic_questions(500))},
        "trends":trend, "funnel":attribution_funnel(days), "governance":keyword_governance(), "internal_links":internal_link_plan(), "decay":content_decay(),
        "technical":technical_seo_status(), "third_party_sources":third_party_source_gaps(), "controller":controller, "alerts":issues,
        "operations":{"connector_health":deepcopy(data.get("connector_health") or {}), "dead_letters":deepcopy((data.get("dead_letters") or [])[-50:]), "daily_budgets":deepcopy(data.get("daily_budgets") or {}), "last_run_at":data.get("last_run_at") or ""},
        "truth":"所有搜索/GEO外部成功必须有真实证据；业务归因只到订单，不采集成交金额、收入、利润或ROI。",
    }
