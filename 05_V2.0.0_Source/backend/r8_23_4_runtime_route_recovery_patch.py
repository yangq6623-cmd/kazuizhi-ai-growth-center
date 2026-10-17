"""R8-23.4 field recovery: fail-open shell, fixed owner routes and legacy-time truth.

This patch is intentionally narrow. It repairs field regressions observed in #70/#72
without weakening GEO Evidence, external Receipt, attribution or finance boundaries.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import r8_23_3_candidate as candidate
from core import seo_geo_growth_intelligence as growth
from core.storage import now_iso

_INSTALLED = False
RECOVERY_VERSION = "R8-23.4 Runtime & Route Recovery"


def _aware_datetime(value):
    """Parse legacy timestamps and always return an aware local datetime."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if stamp.tzinfo is None:
        # Legacy desktop records were written in local wall-clock time.
        stamp = stamp.astimezone()
    return stamp


def _safe_search_rollup(days=30):
    days = int(days if int(days) in growth.ALLOWED_WINDOWS else 30)
    cutoff = datetime.now().astimezone() - timedelta(days=days - 1)
    rows = []
    for item in growth._load().get("search_observations") or []:
        stamp = _aware_datetime(item.get("observed_at"))
        if stamp is not None and stamp >= cutoff:
            rows.append(item)
    latest_truth = {}
    time_totals = defaultdict(lambda: {"impressions": 0, "clicks": 0})
    for item in rows:
        key = (
            item.get("asset_id") or item.get("url"), item.get("engine"),
            item.get("kind"), item.get("keyword") or "",
        )
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
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round(clicks * 100 / impressions, 2) if impressions else None,
        "daily": [
            {
                "date": date,
                **values,
                "ctr": round(values["clicks"] * 100 / values["impressions"], 2)
                if values["impressions"] else None,
            }
            for date, values in sorted(time_totals.items())
        ],
    }


def _safe_attribution_funnel(days=30):
    days = int(days if int(days) in growth.ALLOWED_WINDOWS else 30)
    cutoff = datetime.now().astimezone() - timedelta(days=days - 1)
    counts = Counter()
    sources = defaultdict(Counter)
    for row in growth._load().get("attribution_events") or []:
        stamp = _aware_datetime(row.get("at"))
        if stamp is None or stamp < cutoff:
            continue
        stage = row.get("stage")
        counts[stage] += 1
        sources[str(row.get("source_tracking_id") or "")][stage] += 1
    return {
        "window_days": days,
        "site_visit": counts["site_visit"],
        "mini_program_visit": counts["mini_program_visit"],
        "consultation": counts["consultation"],
        "task_published": counts["task_published"],
        "order": counts["order"],
        "by_source": {key: dict(value) for key, value in sources.items()},
    }


def _version_payload():
    """Ultra-light version endpoint: no model, database or external connector calls."""
    base = dict(server.get_version())
    base.update({
        "alive": True,
        "phase": RECOVERY_VERSION,
        "release": RECOVERY_VERSION,
        "candidate_compatibility": candidate.CANDIDATE_VERSION,
        "runtime_identity": getattr(server, "BUILD_ID", base.get("build_id") or ""),
        "api_contract": "r8-23.4",
        "generated_at": now_iso(),
    })
    return base


def _serve_index(handler):
    """Serve a usable shell immediately. Runtime/readiness checks happen in background."""
    source = (server.get_web_path() / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        "<title>卡嘴子 AI 增长运营中心 V2.0.0 Beta R7 Final</title>",
        "<title>卡嘴子 AI 自治运营 · R8-23.4</title>",
        1,
    )
    source = source.replace("V2.0.0 Beta R7 Final", "R8-23.4 Runtime & Route Recovery")
    source = source.replace(
        'data-page="promotion" data-title="内容增长"',
        'data-page="promotion" data-title="内容生产与发布"',
        1,
    )
    source = source.replace("<span>✦</span>内容增长", "<span>✦</span>内容生产与发布", 1)
    # Guarantee the R8 runtime bundle is present even if an older static shell is reused.
    if "autonomous-ops.js" not in source:
        source = source.replace("</body>", '<script src="/autonomous-ops.js"></script></body>', 1)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _serve_autonomous_ops(handler):
    """Keep the proven runtime, remove the #72 hard boot/wrong-route frontend only."""
    web = server.get_web_path()
    names = [
        "autonomous-ops.js",
        "r8_13_seo_geo_bridge.js",
        "r8_22_autonomy.js",
        "r8_23_growth_os.js",
        "r8_23_2_pilot.js",
        "r8_23_4_recovery.js",
    ]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    # Repair field data written before timezone-aware timestamps became mandatory.
    growth._search_rollup = _safe_search_rollup
    growth.attribution_funnel = _safe_attribution_funnel

    original_get = server.DashboardHandler.do_GET

    def do_get(handler):
        split = urlsplit(handler.path)
        path = split.path
        try:
            if path in {"/", "/index.html"}:
                _serve_index(handler)
                return
            if path == "/autonomous-ops.js":
                _serve_autonomous_ops(handler)
                return
            if path == "/api/ping":
                handler._json_ok({"alive": True, "phase": RECOVERY_VERSION, "at": now_iso()})
                return
            if path == "/api/version":
                handler._json_ok(_version_payload())
                return
            if path == "/api/r8-23-4/recovery":
                handler._json_ok({
                    "alive": True,
                    "phase": RECOVERY_VERSION,
                    "route_contract": {
                        "seo_geo": "r813-seo-geo",
                        "content_production": "promotion",
                    },
                    "formal_geo_truth": "real external A/B Evidence only",
                    "funds_policy": "human-only",
                    "generated_at": now_iso(),
                })
                return
            if path == "/api/r8-20/seo-geo":
                query = parse_qs(split.query)
                raw_days = (query.get("days") or [30])[0]
                try:
                    days = int(raw_days)
                except (TypeError, ValueError):
                    days = 30
                days = days if days in growth.ALLOWED_WINDOWS else 30
                handler._json_ok(growth.status(days=days))
                return
        except Exception as error:  # Final HTTP boundary must always return JSON.
            handler._json_error(503, f"R8-23.4 runtime recovery: {type(error).__name__}: {error}")
            return
        return original_get(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_r8_23_4_runtime_route_recovery = True
    _INSTALLED = True


install()
