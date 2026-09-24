"""R8-12 monotonic runtime integrity guard.

Protects the current Mission execution lineage from upgrade/restart degradation.
The checkpoint is not a second business source of truth.  It only preserves
already-observed local facts (Mission/Growth/video/plan/receipt indexes).

Rules:
- a same-Growth snapshot with fewer children cannot replace a richer checkpoint;
- partial degradation is repaired, not only a completely empty runtime;
- media candidates are restored only if their local files still exist;
- successful receipts are restored only when they already contain a platform
  Content/Post ID and an http(s) URL;
- a genuinely new Growth starts a new lineage and is never overwritten by the
  previous Mission checkpoint.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from core.storage import data_root, now_iso, read_json, write_json

CHECKPOINT_PATH = "r8_12/runtime_last_good.json"
AUDIT_PATH = "r8_12/runtime_integrity_audit.json"
SCHEMA = "kz.runtime-checkpoint.v1"


def _safe_factory() -> dict:
    try:
        from promotion import content_factory as cf
        value = cf._load()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _safe_ops() -> dict:
    value = read_json("ops/autonomous_ops.json", {})
    return value if isinstance(value, dict) else {}


def _active_mission(ops: dict) -> dict | None:
    missions = [x for x in (ops.get("missions") or []) if isinstance(x, dict)]
    active_id = str(ops.get("active_mission_id") or "").strip()
    if not active_id and isinstance(ops.get("active_mission"), dict):
        active_id = str((ops.get("active_mission") or {}).get("mission_id") or "").strip()
    return next((x for x in missions if str(x.get("mission_id") or "") == active_id), missions[0] if missions else None)


def _candidate_exists(candidate: dict) -> bool:
    if not isinstance(candidate, dict):
        return False
    path = str(candidate.get("local_path") or "").strip()
    if path and Path(path).is_file():
        return True
    return False


def _sanitize_video(video: dict) -> dict:
    row = deepcopy(video)
    candidates = []
    for candidate in row.get("candidates", []) if isinstance(row.get("candidates"), list) else []:
        if not isinstance(candidate, dict):
            continue
        restored = deepcopy(candidate)
        restored["exists"] = _candidate_exists(restored)
        if restored["exists"]:
            candidates.append(restored)
    row["candidates"] = candidates
    if row.get("approved_at") and (row.get("review") or {}).get("decision") == "确认发布" and not candidates:
        row["status"] = "异常待处理"
        row["bottleneck"] = "恢复证据中存在审核记录，但本地 FINAL 成片已不存在，禁止伪造成片或发布"
        row["auto_action"] = "重新生成真实本地成片后再进入审核/发布"
        row["approved_at"] = None
        row["review"] = None
    return row


def _valid_receipt(receipt: dict) -> bool:
    if not isinstance(receipt, dict):
        return False
    if receipt.get("result") != "成功":
        return True
    url = str(receipt.get("url") or "")
    return bool(receipt.get("platform_content_id") and (url.startswith("http://") or url.startswith("https://")))


def _bundle() -> dict | None:
    factory = _safe_factory()
    ops = _safe_ops()
    mission = _active_mission(ops)
    if not isinstance(mission, dict):
        return None
    growth_id = str(mission.get("growth_id") or "").strip()
    mission_id = str(mission.get("mission_id") or "").strip()
    if not growth_id or not mission_id:
        return None
    campaigns = [deepcopy(x) for x in factory.get("campaigns", []) if isinstance(x, dict) and x.get("id") == growth_id]
    videos = [_sanitize_video(x) for x in factory.get("videos", []) if isinstance(x, dict) and x.get("campaign_id") == growth_id]
    plans = [deepcopy(x) for x in factory.get("publication_plans", []) if isinstance(x, dict) and x.get("campaign_id") == growth_id]
    plan_ids = {x.get("id") for x in plans if x.get("id")}
    receipts = [deepcopy(x) for x in factory.get("receipts", []) if isinstance(x, dict) and x.get("plan_id") in plan_ids and _valid_receipt(x)]
    return {
        "schema": SCHEMA,
        "saved_at": now_iso(),
        "mission_id": mission_id,
        "growth_id": growth_id,
        "mission": deepcopy(mission),
        "campaigns": campaigns,
        "videos": videos,
        "publication_plans": plans,
        "receipts": receipts,
        "truth_rule": "只保存已存在的本地索引和真实回执；不得据此补造外部成功。",
    }


def _quality(bundle: dict | None) -> tuple[int, int, int, int, int]:
    if not isinstance(bundle, dict):
        return (0, 0, 0, 0, 0)
    videos = [x for x in bundle.get("videos", []) if isinstance(x, dict)]
    approved = sum(1 for x in videos if x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布")
    media = sum(1 for x in videos if any(_candidate_exists(c) for c in (x.get("candidates") or []) if isinstance(c, dict)))
    return (
        len(bundle.get("campaigns") or []),
        len(videos),
        approved + media,
        len(bundle.get("publication_plans") or []),
        len(bundle.get("receipts") or []),
    )


def _append_audit(kind: str, detail: dict) -> None:
    payload = read_json(AUDIT_PATH, {})
    payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("schema", "kz.runtime-integrity-audit.v1")
    payload.setdefault("events", [])
    payload["events"].insert(0, {"at": now_iso(), "kind": kind, "detail": detail})
    payload["events"] = payload["events"][:300]
    payload["updated_at"] = now_iso()
    write_json(AUDIT_PATH, payload)


def checkpoint_runtime(reason="scheduler") -> dict:
    current = _bundle()
    if current is None:
        return {"saved": False, "reason": "no_active_mission"}
    previous = read_json(CHECKPOINT_PATH, {})
    previous = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else None
    if previous and previous.get("growth_id") == current.get("growth_id"):
        if _quality(current) < _quality(previous):
            return {
                "saved": False,
                "reason": "same_growth_snapshot_is_less_complete",
                "current_quality": _quality(current),
                "checkpoint_quality": _quality(previous),
            }
    # Different Growth = intentional new lineage; start a fresh checkpoint.
    current["reason"] = str(reason or "scheduler")[:120]
    write_json(CHECKPOINT_PATH, current)
    return {"saved": True, "mission_id": current["mission_id"], "growth_id": current["growth_id"], "quality": _quality(current)}


def _merge_by_id(current: list, fallback: list, *, id_field="id") -> int:
    existing = {str(x.get(id_field) or ""): x for x in current if isinstance(x, dict)}
    restored = 0
    for candidate in fallback:
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get(id_field) or "")
        if not identifier or identifier in existing:
            continue
        current.append(deepcopy(candidate))
        existing[identifier] = current[-1]
        restored += 1
    return restored


def recover_runtime_if_degraded() -> dict:
    checkpoint = read_json(CHECKPOINT_PATH, {})
    if not isinstance(checkpoint, dict) or checkpoint.get("schema") != SCHEMA:
        return {"restored": False, "reason": "no_runtime_checkpoint"}
    growth_id = str(checkpoint.get("growth_id") or "").strip()
    mission_id = str(checkpoint.get("mission_id") or "").strip()
    if not growth_id or not mission_id:
        return {"restored": False, "reason": "invalid_checkpoint_identity"}

    factory = _safe_factory()
    ops = _safe_ops()
    active = _active_mission(ops)
    current_growth = str((active or {}).get("growth_id") or factory.get("active_campaign_id") or "").strip()
    # A different non-empty Growth is a new business lineage, not degradation.
    if current_growth and current_growth != growth_id:
        return {"restored": False, "reason": "different_active_growth"}

    current_bundle = _bundle()
    if current_bundle is not None and _quality(current_bundle) >= _quality(checkpoint) and str(current_bundle.get("mission_id") or "") == mission_id:
        return {"restored": False, "reason": "runtime_not_degraded"}

    campaigns = factory.setdefault("campaigns", [])
    videos = factory.setdefault("videos", [])
    plans = factory.setdefault("publication_plans", [])
    receipts = factory.setdefault("receipts", [])
    restored_campaigns = _merge_by_id(campaigns, checkpoint.get("campaigns") or [])
    safe_videos = [_sanitize_video(x) for x in checkpoint.get("videos", []) if isinstance(x, dict)]
    restored_videos = _merge_by_id(videos, safe_videos)
    restored_plans = _merge_by_id(plans, checkpoint.get("publication_plans") or [])
    safe_receipts = [x for x in checkpoint.get("receipts", []) if _valid_receipt(x)]
    restored_receipts = _merge_by_id(receipts, safe_receipts)
    factory["active_campaign_id"] = growth_id

    from promotion import content_factory as cf
    cf._save(factory)

    missions = ops.setdefault("missions", [])
    by_growth = next((x for x in missions if isinstance(x, dict) and x.get("growth_id") == growth_id), None)
    old_mission = deepcopy(checkpoint.get("mission") or {})
    restored_mission = 0
    repaired_identity = False
    if by_growth is None:
        missions.insert(0, old_mission)
        restored_mission = 1
    else:
        # Same Growth should keep the last-known-good Mission identity.  This
        # closes upgrade-generated Mission ID drift without touching a new Growth.
        if str(by_growth.get("mission_id") or "") != mission_id:
            by_growth["mission_id"] = mission_id
            repaired_identity = True
        for field, value in old_mission.items():
            if by_growth.get(field) in {None, "", [], {}} and value not in {None, "", [], {}}:
                by_growth[field] = deepcopy(value)
    ops["active_mission_id"] = mission_id
    ops["updated_at"] = now_iso()
    write_json("ops/autonomous_ops.json", ops)

    changed = any((restored_campaigns, restored_videos, restored_plans, restored_receipts, restored_mission, repaired_identity))
    if changed:
        detail = {
            "mission_id": mission_id,
            "growth_id": growth_id,
            "campaigns": restored_campaigns,
            "videos": restored_videos,
            "plans": restored_plans,
            "receipts": restored_receipts,
            "mission": restored_mission,
            "mission_identity_repaired": repaired_identity,
        }
        _append_audit("partial_runtime_recovery", detail)
        return {"restored": True, **detail}
    return {"restored": False, "reason": "degraded_but_nothing_safe_to_restore"}
