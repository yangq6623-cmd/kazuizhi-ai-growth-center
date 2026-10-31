"""R8-12 monotonic Mission execution checkpoint + partial recovery.

A same-Growth runtime may advance, but upgrade/restart noise must not silently
erase Mission identity, videos, publication plans or verified receipts. A new
Growth is treated as a new business lineage and is never overwritten by the old
checkpoint.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from core.storage import now_iso, read_json, write_json

CHECKPOINT_PATH = "r8_12/runtime_last_good.json"
AUDIT_PATH = "r8_12/runtime_integrity_audit.json"
SCHEMA = "kz.runtime-checkpoint.v1"


def _missing(value):
    return value is None or value == "" or value == [] or value == {}


def _safe_factory():
    try:
        from promotion import content_factory as cf
        value = cf._load()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _safe_ops():
    value = read_json("ops/autonomous_ops.json", {})
    return value if isinstance(value, dict) else {}


def _active_mission(ops):
    missions = [x for x in (ops.get("missions") or []) if isinstance(x, dict)]
    active_id = str(ops.get("active_mission_id") or "").strip()
    if not active_id and isinstance(ops.get("active_mission"), dict):
        active_id = str((ops.get("active_mission") or {}).get("mission_id") or "").strip()
    return next((x for x in missions if str(x.get("mission_id") or "") == active_id), missions[0] if missions else None)


def _candidate_exists(candidate):
    if not isinstance(candidate, dict): return False
    path = str(candidate.get("local_path") or "").strip()
    return bool(path and Path(path).is_file())


def _sanitize_video(video):
    row = deepcopy(video)
    candidates = []
    for candidate in row.get("candidates", []) if isinstance(row.get("candidates"), list) else []:
        if not isinstance(candidate, dict): continue
        restored = deepcopy(candidate); restored["exists"] = _candidate_exists(restored)
        if restored["exists"]: candidates.append(restored)
    row["candidates"] = candidates
    if row.get("approved_at") and (row.get("review") or {}).get("decision") == "确认发布" and not candidates:
        row.update({
            "status": "异常待处理",
            "bottleneck": "恢复记录有审核证据，但本地 FINAL 成片已不存在，禁止伪造成片或发布",
            "auto_action": "重新生成真实本地成片后再进入审核/发布",
            "approved_at": None,
            "review": None,
        })
    return row


def _valid_receipt(receipt):
    if not isinstance(receipt, dict): return False
    if receipt.get("result") != "成功": return True
    url = str(receipt.get("url") or "")
    return bool(receipt.get("platform_content_id") and (url.startswith("http://") or url.startswith("https://")))


def _bundle():
    factory, ops = _safe_factory(), _safe_ops()
    mission = _active_mission(ops)
    if not isinstance(mission, dict): return None
    growth_id, mission_id = str(mission.get("growth_id") or "").strip(), str(mission.get("mission_id") or "").strip()
    if not growth_id or not mission_id: return None
    campaigns = [deepcopy(x) for x in factory.get("campaigns", []) if isinstance(x, dict) and x.get("id") == growth_id]
    videos = [_sanitize_video(x) for x in factory.get("videos", []) if isinstance(x, dict) and x.get("campaign_id") == growth_id]
    plans = [deepcopy(x) for x in factory.get("publication_plans", []) if isinstance(x, dict) and x.get("campaign_id") == growth_id]
    plan_ids = {x.get("id") for x in plans if x.get("id")}
    receipts = [deepcopy(x) for x in factory.get("receipts", []) if isinstance(x, dict) and x.get("plan_id") in plan_ids and _valid_receipt(x)]
    return {
        "schema": SCHEMA, "saved_at": now_iso(), "mission_id": mission_id, "growth_id": growth_id,
        "mission": deepcopy(mission), "campaigns": campaigns, "videos": videos,
        "publication_plans": plans, "receipts": receipts,
        "truth_rule": "只保存已存在本地证据与真实回执；不得据此补造外部成功。",
    }


def _quality(bundle):
    if not isinstance(bundle, dict): return (0, 0, 0, 0, 0)
    videos = [x for x in bundle.get("videos", []) if isinstance(x, dict)]
    approved = sum(1 for x in videos if x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布")
    media = sum(1 for x in videos if any(_candidate_exists(c) for c in (x.get("candidates") or []) if isinstance(c, dict)))
    return (len(bundle.get("campaigns") or []), len(videos), approved + media, len(bundle.get("publication_plans") or []), len(bundle.get("receipts") or []))


def _append_audit(kind, detail):
    payload = read_json(AUDIT_PATH, {})
    payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("schema", "kz.runtime-integrity-audit.v1"); payload.setdefault("events", [])
    payload["events"].insert(0, {"at": now_iso(), "kind": kind, "detail": detail})
    payload["events"] = payload["events"][:300]; payload["updated_at"] = now_iso()
    write_json(AUDIT_PATH, payload)


def checkpoint_runtime(reason="scheduler"):
    current = _bundle()
    if current is None: return {"saved": False, "reason": "no_active_mission"}
    previous = read_json(CHECKPOINT_PATH, {})
    previous = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else None
    same_growth = bool(previous and previous.get("growth_id") == current.get("growth_id"))
    if same_growth and str(previous.get("mission_id") or "") != str(current.get("mission_id") or ""):
        detail = {
            "growth_id": current.get("growth_id"),
            "stable_mission_id": previous.get("mission_id"),
            "rejected_mission_id": current.get("mission_id"),
            "checkpoint_reason": str(reason or "scheduler")[:120],
        }
        _append_audit("mission_identity_drift_blocked", detail)
        return {"saved": False, "reason": "same_growth_mission_identity_drift", **detail}
    if same_growth and _quality(current) < _quality(previous):
        return {"saved": False, "reason": "same_growth_snapshot_is_less_complete", "current_quality": _quality(current), "checkpoint_quality": _quality(previous)}
    current["reason"] = str(reason or "scheduler")[:120]
    write_json(CHECKPOINT_PATH, current)
    return {"saved": True, "mission_id": current["mission_id"], "growth_id": current["growth_id"], "quality": _quality(current)}


def _merge_by_id(current, fallback, id_field="id"):
    existing = {str(x.get(id_field) or ""): x for x in current if isinstance(x, dict)}
    restored = 0
    for candidate in fallback:
        if not isinstance(candidate, dict): continue
        identifier = str(candidate.get(id_field) or "")
        if not identifier or identifier in existing: continue
        current.append(deepcopy(candidate)); existing[identifier] = current[-1]; restored += 1
    return restored


def _canonicalize_same_growth_missions(ops, growth_id, mission_id, checkpoint_mission):
    missions = [x for x in (ops.get("missions") or []) if isinstance(x, dict)]
    same_growth = [x for x in missions if str(x.get("growth_id") or "") == growth_id]
    canonical = deepcopy(same_growth[0] if same_growth else checkpoint_mission or {})
    created = 0 if same_growth else 1
    repaired = False
    if str(canonical.get("mission_id") or "") != mission_id:
        canonical["mission_id"] = mission_id
        repaired = True
    canonical["growth_id"] = growth_id
    for field, value in (checkpoint_mission or {}).items():
        if _missing(canonical.get(field)) and not _missing(value):
            canonical[field] = deepcopy(value)
    others = [x for x in missions if str(x.get("growth_id") or "") != growth_id]
    deduped = max(0, len(same_growth) - 1)
    ops["missions"] = [canonical] + others
    return canonical, created, repaired, deduped


def recover_runtime_if_degraded():
    checkpoint = read_json(CHECKPOINT_PATH, {})
    if not isinstance(checkpoint, dict) or checkpoint.get("schema") != SCHEMA:
        return {"restored": False, "reason": "no_runtime_checkpoint"}
    growth_id, mission_id = str(checkpoint.get("growth_id") or "").strip(), str(checkpoint.get("mission_id") or "").strip()
    if not growth_id or not mission_id: return {"restored": False, "reason": "invalid_checkpoint_identity"}

    factory, ops = _safe_factory(), _safe_ops()
    active = _active_mission(ops)
    current_growth = str((active or {}).get("growth_id") or factory.get("active_campaign_id") or "").strip()
    if current_growth and current_growth != growth_id:
        return {"restored": False, "reason": "different_active_growth"}
    current = _bundle()
    if current is not None and _quality(current) >= _quality(checkpoint) and str(current.get("mission_id") or "") == mission_id:
        return {"restored": False, "reason": "runtime_not_degraded"}

    campaigns, videos = factory.setdefault("campaigns", []), factory.setdefault("videos", [])
    plans, receipts = factory.setdefault("publication_plans", []), factory.setdefault("receipts", [])
    rc = _merge_by_id(campaigns, checkpoint.get("campaigns") or [])
    rv = _merge_by_id(videos, [_sanitize_video(x) for x in checkpoint.get("videos", []) if isinstance(x, dict)])
    rp = _merge_by_id(plans, checkpoint.get("publication_plans") or [])
    rr = _merge_by_id(receipts, [x for x in checkpoint.get("receipts", []) if _valid_receipt(x)])
    factory["active_campaign_id"] = growth_id
    from promotion import content_factory as cf
    cf._save(factory)

    old = deepcopy(checkpoint.get("mission") or {})
    canonical, rm, repaired, deduped = _canonicalize_same_growth_missions(ops, growth_id, mission_id, old)
    ops["active_mission_id"] = mission_id
    if isinstance(ops.get("active_mission"), dict): ops["active_mission"] = deepcopy(canonical)
    ops["updated_at"] = now_iso()
    write_json("ops/autonomous_ops.json", ops)

    changed = any((rc, rv, rp, rr, rm, repaired, deduped))
    if changed:
        detail = {
            "mission_id": mission_id,
            "growth_id": growth_id,
            "campaigns": rc,
            "videos": rv,
            "plans": rp,
            "receipts": rr,
            "mission": rm,
            "mission_identity_repaired": repaired,
            "deduped_same_growth_missions": deduped,
        }
        _append_audit("partial_runtime_recovery", detail)
        return {"restored": True, **detail}
    return {"restored": False, "reason": "degraded_but_nothing_safe_to_restore"}
