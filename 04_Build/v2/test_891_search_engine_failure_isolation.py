"""Isolate IndexNow initialization faults without making external requests."""
import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
AUTONOMY = ROOT / "core" / "seo_geo_autonomy.py"
SUBMITTER = ROOT / "integrations" / "search_engine_submitter.py"


def find_function(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return next(row for row in tree.body if isinstance(row, ast.FunctionDef) and row.name == name)


def test_autonomy_lane():
    function = find_function(AUTONOMY, "run_once")
    branch = next(row for row in ast.walk(function)
                  if isinstance(row, ast.If)
                  and isinstance(row.test, ast.BoolOp)
                  and "ready_search_connectors" in ast.unparse(row.test)
                  and "publish_connector_ready" in ast.unparse(row.test))
    calls, notices = [], {}

    def initialize():
        calls.append("indexnow_init")
        raise OSError("managed key file inaccessible")

    def submit_pending(limit):
        calls.append("search_submit")
        return {"submitted_count": 1, "failed": []}

    scope = {
        "readiness": {"publish_connector_ready": True, "ready_search_connectors": ["google_search_console"]},
        "search_engine_submitter": SimpleNamespace(
            initialize_indexnow=initialize, submit_pending=submit_pending,
            status=lambda: {"ready_engines": ["google_search_console"]}),
        "data": {},
        "_add_human_item": lambda data, key, *args: notices.__setitem__(key, args),
        "_close_human_item": lambda data, key: notices.pop(key, None),
    }
    exec(compile(ast.Module(body=[branch], type_ignores=[]), str(AUTONOMY), "exec"), scope)
    assert calls == ["indexnow_init", "search_submit"], calls
    assert scope["search_submit"]["submitted_count"] == 1
    assert "seo_indexnow_initialization_error" in notices


def test_submitter_lane(failure):
    function = find_function(SUBMITTER, "submit_pending")
    submitted = []
    asset = {"id": "SEO-TEST", "public_url": "https://example.invalid/seo/test"}

    def initialize():
        if failure == "init":
            raise OSError("managed key file inaccessible")
        return {"ok": True, "verification": {"ok": True}}

    def key():
        if failure == "key":
            raise OSError("managed key unavailable")
        return "test-key"

    def eligible(data, engine, assets, limit):
        return ([asset] if engine == "google_search_console" else [], [])

    scope = {
        "MAX_SUBMISSION_BATCH": 3,
        "_load": lambda: {"site_url": "https://example.invalid/", "allow_baidu_http_submission": False},
        "now_iso": lambda: "2026-11-01T00:00:00+00:00",
        "_public_assets": lambda: [asset],
        "seo_public_deployer": SimpleNamespace(publication_scope_allowed=lambda row: True,
                                                status=lambda: {"ready": True}),
        "_batch_limit": lambda limit: limit,
        "_baidu_quota_held_today": lambda data: False,
        "_eligible_assets": eligible,
        "_https_url": lambda value, name: value,
        "initialize_indexnow": initialize,
        "_indexnow_key": key,
        "_connected_account": lambda engine: {"id": "already-authorized"} if engine == "google_search_console" else None,
        "_google_access_token": lambda account: "test-token",
        "_google_refresh_available": lambda account: False,
        "_google_token_near_expiry": lambda account: False,
        "_submit_google_sitemap": lambda *args: {"ok": True, "status": 200},
        "_record_attempt": lambda *args: None,
        "_append_receipt": lambda *args: None,
        "_record_success": lambda *args: None,
        "_record_submission": lambda asset, engine, receipt: submitted.append(engine),
        "_baidu_token": lambda: "",
        "_retry_queue_count": lambda data: 0,
        "_save": lambda data: None,
        "urllib": __import__("urllib"),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SUBMITTER), "exec"), scope)
    result = scope["submit_pending"]()
    assert submitted == ["google_search_console"], submitted
    assert result["submitted_count"] == 1
    assert result["indexnow_initialization"]["reason"] == (
        "indexnow_initialization_error" if failure == "init" else "indexnow_key_unavailable")


test_autonomy_lane()
test_submitter_lane("init")
test_submitter_lane("key")
print("PASS: IndexNow setup failure does not suppress an independently ready search connector")
