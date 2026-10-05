"""R8-16 truthful search-engine submission connectors.

This module advances verified public SEO assets from PUBLISHED to SUBMITTED only
when an external search endpoint returns an observable acceptance response.

Supported paths:
- IndexNow: automatic key generation/hosting inside the guarded /seo/ subtree and
  batch URL submission to the official IndexNow endpoint.
- Google Search Console: sitemap submission through an actually authorized GSC
  account stored by the R8-12 OAuth/DPAPI account center.
- Baidu Search Resource Platform: optional API submission using the site's own
  token. Baidu's documented endpoint is HTTP, so this path is opt-in and the token
  remains in the local DPAPI vault rather than project files/logs.

A successful submission receipt is not treated as crawl/index/rank evidence.

Submission is deliberately conservative: only versioned public pages are
eligible, a page/version is attempted at most once per engine per natural day,
and every external batch is capped at three URLs.  This keeps a rejected
endpoint (especially a Baidu quota response) from repeatedly consuming work on
the same historical inventory.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from core.storage import now_iso, read_json, write_json
from core.seo_geo_growth import STAGE_INDEX, dashboard, record_asset_stage
from integrations.credential_vault import get_secret, put_secret
from integrations import seo_public_deployer

STORE = "r8_16/search_submitter.json"
RECEIPTS = "r8_16/search_submission_receipts.json"
REGISTRY = "r8_12/account_registry.json"
SCHEMA = "kz.search-submitter.v1"
DEFAULT = {
    "schema": SCHEMA,
    "site_url": "https://kazuizhi.com/",
    # The verified Search Console resource is a domain property, not a
    # URL-prefix property.  Google requires the same identifier for Sitemap
    # API writes that it exposes in Search Console (sc-domain:...).
    "google_site_url": "sc-domain:kazuizhi.com",
    "baidu_site": "kazuizhi.com",
    "allow_baidu_http_submission": False,
    "indexnow_endpoint": "https://api.indexnow.org/indexnow",
    "updated_at": "",
    "last_run_at": "",
    "last_result": {},
    "last_indexnow_initialization": {},
    "submission_attempts": {},
    # A recovered asset may already have an independently verified public URL
    # from a previous installer, but no local submission receipt.  It is safe
    # to backfill that narrow case once, in normal capped batches; this is not
    # a blanket retry of arbitrary historical pages.
    "allow_verified_receipt_backfill": True,
}

MAX_SUBMISSION_BATCH = 3


def _load() -> dict:
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    for key, value in DEFAULT.items():
        data.setdefault(key, deepcopy(value))
    # Migrate the previous URL-prefix default so existing local installs do
    # not keep submitting against a different Search Console property.
    if data.get("google_site_url") == "https://kazuizhi.com/":
        data["google_site_url"] = DEFAULT["google_site_url"]
    _normalize_baidu_quota_failure(data)
    return data


def _save(data: dict) -> dict:
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _https_url(value: str, field: str) -> str:
    raw = str(value or "").strip()
    parts = urlsplit(raw)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError(f"{field} 必须是有效 HTTPS 地址")
    return raw.rstrip("/") + "/"


def _google_site_property(value: str) -> str:
    raw = str(value or "").strip()
    if raw.startswith("sc-domain:"):
        domain = raw.split(":", 1)[1].strip().lower()
        if not re.fullmatch(r"[a-z0-9.-]+", domain) or "." not in domain:
            raise ValueError("Google 域名资源格式不正确")
        return f"sc-domain:{domain}"
    return _https_url(raw, "google_site_url")


def _vault_get(key: str, env_name: str = "") -> str:
    env_value = str(os.environ.get(env_name, "") if env_name else "").strip()
    if env_value:
        return env_value
    try:
        return str(get_secret(key) or "").strip()
    except (OSError, RuntimeError, ValueError):
        return ""


def _vault_put(key: str, value: str) -> None:
    put_secret(key, str(value or "").strip())


def _indexnow_key() -> str:
    return _vault_get("search.indexnow.key", "KZ_INDEXNOW_KEY")


def _baidu_token() -> str:
    return _vault_get("search.baidu.site_token", "KZ_BAIDU_SITE_TOKEN")


def _valid_indexnow_key(value: str) -> bool:
    raw = str(value or "").strip()
    return bool(8 <= len(raw) <= 128 and re.fullmatch(r"[A-Za-z0-9-]+", raw))


def _connected_account(platform: str) -> dict | None:
    registry = read_json(REGISTRY, {})
    accounts = registry.get("accounts") if isinstance(registry, dict) else []
    candidates: list[dict] = []
    for row in accounts or []:
        if not isinstance(row, dict) or row.get("platform") != platform:
            continue
        auth = row.get("auth") if isinstance(row.get("auth"), dict) else {}
        if auth.get("status") == "connected" and not auth.get("reauthorization_required"):
            candidates.append(row)
    if not candidates:
        return None

    # OAuth consent may be repeated for the same real Google account.  Each
    # callback is intentionally recorded as a durable account asset, so the
    # registry can contain older access tokens beside the freshly authorized
    # one.  Never pick the first historical row: prefer the most recently
    # verified usable token, then fall back to the newest connected row for a
    # truthful "needs reauthorization" response.
    candidates.sort(
        key=lambda row: str((row.get("auth") or {}).get("last_verified_at") or row.get("updated_at") or ""),
        reverse=True,
    )
    for row in candidates:
        if _vault_get(f"oauth.{row.get('account_id')}.access_token"):
            return deepcopy(row)
    return deepcopy(candidates[0])


def _google_access_token(account: dict | None) -> str:
    if not account:
        return ""
    return _vault_get(f"oauth.{account.get('account_id')}.access_token")


def _append_receipt(row: dict) -> None:
    data = read_json(RECEIPTS, {"schema": "kz.search-submission-receipts.v1", "items": []})
    if not isinstance(data, dict):
        data = {"schema": "kz.search-submission-receipts.v1", "items": []}
    data.setdefault("items", []).insert(0, row)
    data["items"] = data["items"][:1000]
    data["updated_at"] = now_iso()
    write_json(RECEIPTS, data)


def _existing_engine_receipt(asset: dict, engine: str) -> bool:
    return any(
        isinstance(row, dict) and str(row.get("engine") or "") == engine
        for row in (asset.get("submission_receipts") or [])
    )


def _record_submission(asset: dict, engine: str, receipt_id: str) -> None:
    current = str(asset.get("stage") or "PUBLISHED")
    if STAGE_INDEX.get(current, 0) <= STAGE_INDEX["SUBMITTED"]:
        record_asset_stage(asset["id"], "SUBMITTED", {"engine": engine, "receipt": receipt_id})


def _public_assets() -> list[dict]:
    snap = dashboard()
    assets = []
    for row in snap.get("assets", []):
        if not isinstance(row, dict):
            continue
        stage = str(row.get("stage") or "DISCOVERED")
        if STAGE_INDEX.get(stage, 0) < STAGE_INDEX["PUBLISHED"]:
            continue
        url = str(row.get("public_url") or "").strip()
        if url.startswith("https://"):
            assets.append(row)
    return assets


def _submission_revision(asset: dict) -> str:
    """Return the public version marker used to decide whether an asset is new.

    ``updated_at`` cannot be used here because recording a search receipt also
    updates it.  ``published_at`` is only written after a real public URL has
    been verified, so it is a stable marker for a newly published page.
    """
    return str(asset.get("published_at") or "").strip()


def _batch_limit(limit: int | None) -> int:
    return max(1, min(MAX_SUBMISSION_BATCH, int(limit or MAX_SUBMISSION_BATCH)))


def _attempted_today(data: dict, engine: str, asset: dict) -> bool:
    attempts = data.get("submission_attempts") or {}
    entry = ((attempts.get(engine) or {}).get(str(asset.get("id"))) or {})
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("date") == now_iso().split("T", 1)[0]
        and entry.get("revision") == _submission_revision(asset)
    )


def _record_attempt(data: dict, engine: str, assets: list[dict]) -> None:
    attempts = data.setdefault("submission_attempts", {}).setdefault(engine, {})
    today = now_iso().split("T", 1)[0]
    for asset in assets:
        attempts[str(asset.get("id"))] = {
            "date": today,
            "revision": _submission_revision(asset),
        }


def _eligible_assets(data: dict, engine: str, assets: list[dict], limit: int) -> tuple[list[dict], int]:
    """Return at most ``limit`` fresh page revisions for one search engine.

    Pre-existing public records without ``published_at`` normally stay outside
    the automatic queue.  The single exception is an asset recovered from an
    immutable, verified deployment receipt: it can receive one capped search
    submission because it is a genuine public page whose local ledger was
    restored after an upgrade, not an arbitrary historic retry.
    """
    legacy = 0
    eligible = []
    for asset in assets:
        recovered = any(
            isinstance(event, dict)
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("recovered_from_verified_receipt")
            for event in (asset.get("events") or [])
        )
        if not _submission_revision(asset) and not (
            data.get("allow_verified_receipt_backfill", True) and recovered
        ):
            legacy += 1
            continue
        if _existing_engine_receipt(asset, engine) or _attempted_today(data, engine, asset):
            continue
        eligible.append(asset)
    eligible.sort(key=lambda asset: _submission_revision(asset), reverse=True)
    return eligible[:limit], legacy


def _baidu_quota_exhausted(result: dict) -> bool:
    response = result.get("response") if isinstance(result, dict) else ""
    if isinstance(response, dict):
        response = " ".join(str(value) for value in response.values())
    # Older local records sometimes stored the decoded Baidu payload directly
    # under ``result`` rather than under ``response``.
    detail = response if response else result
    return "over quota" in str(detail or "").lower()


def _normalize_baidu_quota_failure(data: dict) -> None:
    """Upgrade older saved results to the explicit quota state.

    R8-17 installs may already contain a same-day ``api_submit_failed`` record
    whose Baidu payload says ``over quota``.  Preserve that evidence, but label
    it correctly so a first run after the upgrade does not retry it.
    """
    last = data.get("last_result") or {}
    for failure in last.get("failed") or []:
        if (
            isinstance(failure, dict)
            and failure.get("engine") == "baidu"
            and _baidu_quota_exhausted(failure.get("result") or {})
        ):
            failure["reason"] = "baidu_quota_exhausted"


def _baidu_quota_held_today(data: dict) -> bool:
    last = data.get("last_result") or {}
    if str(data.get("last_run_at") or "").split("T", 1)[0] != now_iso().split("T", 1)[0]:
        return False
    return any(
        isinstance(failure, dict)
        and failure.get("engine") == "baidu"
        and failure.get("reason") == "baidu_quota_exhausted"
        for failure in (last.get("failed") or [])
    )


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".kz-indexnow-", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _ensure_indexnow_key_file(key: str, timeout: int = 8) -> dict:
    deploy = seo_public_deployer.status()
    if not deploy.get("ready"):
        return {"ok": False, "reason": deploy.get("reason") or "public_deploy_not_ready"}
    root = Path(str(deploy.get("site_root") or ""))
    if not root.is_absolute() or not root.exists():
        return {"ok": False, "reason": "site_root_not_available"}
    managed = root / "seo"
    destination = managed / f"{key}.txt"
    _atomic_text(destination, key)
    base = str(deploy.get("public_base_url") or "").rstrip("/") + "/"
    public_url = urllib.parse.urljoin(base, f"seo/{key}.txt")
    request = urllib.request.Request(public_url, headers={"User-Agent": "Kazuizhi-R8-16-IndexNow/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - validated HTTPS public URL
            status_code = int(getattr(response, "status", 200) or 200)
            body = response.read(4096).decode("utf-8", errors="replace").strip()
        ok = 200 <= status_code < 300 and body == key
        return {"ok": ok, "status": status_code, "key_location": public_url, "checked_at": now_iso()}
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "key_location": public_url, "checked_at": now_iso()}


def initialize_indexnow() -> dict:
    """Create and verify the managed IndexNow key before a submission attempt.

    This is deliberately separate from ``status``: reading a dashboard must not
    create secrets or write to a public site.  The autonomous worker calls this
    once the guarded public deploy connector is ready, and persists only
    non-secret verification metadata for the owner-facing status card.
    """
    data = _load()
    deploy = seo_public_deployer.status()
    result = {
        "ok": False,
        "initialized": False,
        "key_created": False,
        "checked_at": now_iso(),
    }
    if not deploy.get("ready"):
        result["reason"] = deploy.get("reason") or "public_deploy_not_ready"
        data["last_indexnow_initialization"] = result
        _save(data)
        return result

    key = _indexnow_key()
    if not key:
        try:
            key = secrets.token_hex(16)
            _vault_put("search.indexnow.key", key)
            result["key_created"] = True
        except (OSError, RuntimeError, ValueError) as error:
            result["reason"] = "key_generation_failed"
            result["error"] = str(error)
            data["last_indexnow_initialization"] = result
            _save(data)
            return result
    if not _valid_indexnow_key(key):
        result["reason"] = "invalid_indexnow_key"
        data["last_indexnow_initialization"] = result
        _save(data)
        return result

    verification = _ensure_indexnow_key_file(key)
    result.update({
        "ok": bool(verification.get("ok")),
        "initialized": True,
        "key_location": verification.get("key_location"),
        "verification": verification,
    })
    if not result["ok"]:
        result["reason"] = "key_file_public_verification_failed"
    data["last_indexnow_initialization"] = result
    _save(data)
    return result


def _submit_indexnow(urls: list[str], key: str, key_location: str, endpoint: str, timeout: int = 15) -> dict:
    host = urlsplit(urls[0]).netloc
    payload = {"host": host, "key": key, "keyLocation": key_location, "urlList": urls[:10000]}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "Kazuizhi-R8-16/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - configured official HTTPS endpoint
            code = int(getattr(response, "status", 200) or 200)
            response_body = response.read(16 * 1024).decode("utf-8", errors="replace")
        return {"ok": code in {200, 202}, "status": code, "response": response_body[:2000], "submitted": len(urls), "at": now_iso()}
    except urllib.error.HTTPError as error:
        response_body = error.read(16 * 1024).decode("utf-8", errors="replace") if getattr(error, "fp", None) else ""
        return {"ok": False, "status": int(error.code), "response": response_body[:2000], "error": str(error), "at": now_iso()}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "at": now_iso()}


def _submit_google_sitemap(site_url: str, sitemap_url: str, access_token: str, timeout: int = 20) -> dict:
    site = urllib.parse.quote(site_url, safe="")
    feed = urllib.parse.quote(sitemap_url, safe="")
    endpoint = f"https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps/{feed}"
    request = urllib.request.Request(
        endpoint,
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json", "User-Agent": "Kazuizhi-R8-16/1.0"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed Google HTTPS endpoint
            code = int(getattr(response, "status", 204) or 204)
            body = response.read(16 * 1024).decode("utf-8", errors="replace")
        return {"ok": 200 <= code < 300, "status": code, "response": body[:2000], "sitemap": sitemap_url, "at": now_iso()}
    except urllib.error.HTTPError as error:
        body = error.read(16 * 1024).decode("utf-8", errors="replace") if getattr(error, "fp", None) else ""
        return {"ok": False, "status": int(error.code), "response": body[:2000], "error": str(error), "sitemap": sitemap_url, "at": now_iso()}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "sitemap": sitemap_url, "at": now_iso()}


def _submit_baidu(urls: list[str], site: str, token: str, timeout: int = 15) -> dict:
    endpoint = "http://data.zz.baidu.com/urls?" + urllib.parse.urlencode({"site": site, "token": token})
    body = "\n".join(urls).encode("utf-8")
    request = urllib.request.Request(endpoint, data=body, headers={"Content-Type": "text/plain", "User-Agent": "Kazuizhi-R8-16/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - Baidu documents this HTTP endpoint
            code = int(getattr(response, "status", 200) or 200)
            raw = response.read(32 * 1024).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:2000]}
        ok = bool(200 <= code < 300 and isinstance(payload, dict) and not payload.get("error"))
        return {"ok": ok, "status": code, "response": payload, "submitted": len(urls), "at": now_iso()}
    except urllib.error.HTTPError as error:
        raw = error.read(16 * 1024).decode("utf-8", errors="replace") if getattr(error, "fp", None) else ""
        return {"ok": False, "status": int(error.code), "response": raw[:2000], "error": str(error), "at": now_iso()}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "at": now_iso()}


def configure(payload: dict) -> dict:
    data = _load()
    if "site_url" in payload:
        data["site_url"] = _https_url(payload.get("site_url"), "site_url")
    if "google_site_url" in payload:
        data["google_site_url"] = _google_site_property(payload.get("google_site_url"))
    if "baidu_site" in payload:
        value = str(payload.get("baidu_site") or "").strip().lower()
        if not value or "/" in value or ":" in value:
            raise ValueError("baidu_site 只填写已验证站点域名，例如 kazuizhi.com")
        data["baidu_site"] = value
    if "allow_baidu_http_submission" in payload:
        data["allow_baidu_http_submission"] = bool(payload.get("allow_baidu_http_submission"))
    if "indexnow_key" in payload and str(payload.get("indexnow_key") or "").strip():
        key = str(payload.get("indexnow_key") or "").strip()
        if not _valid_indexnow_key(key):
            raise ValueError("IndexNow key 必须为 8-128 位字母/数字/短横线")
        _vault_put("search.indexnow.key", key)
    if payload.get("generate_indexnow_key"):
        key = secrets.token_hex(16)
        _vault_put("search.indexnow.key", key)
    if "baidu_token" in payload and str(payload.get("baidu_token") or "").strip():
        _vault_put("search.baidu.site_token", str(payload.get("baidu_token") or "").strip())
    _save(data)
    return status()


def status() -> dict:
    data = _load()
    deploy = seo_public_deployer.status()
    index_key = _indexnow_key()
    google_account = _connected_account("google_search_console")
    google_token = _google_access_token(google_account)
    google_auth_error = _google_oauth_reauthorization_required(data.get("last_result") or {})
    google_ready = bool(google_account and google_token and not google_auth_error)
    baidu_token = _baidu_token()
    assets = _public_assets()
    indexnow_init = deepcopy(data.get("last_indexnow_initialization") or {})
    indexnow_ready = bool(index_key and deploy.get("ready") and indexnow_init.get("ok"))
    return {
        "site_url": data.get("site_url"),
        "public_pages": len(assets),
        "connectors": {
            "baidu": {
                "label": "百度搜索资源平台",
                "configured": bool(baidu_token),
                "ready": bool(baidu_token and data.get("allow_baidu_http_submission")),
                "mode": "普通收录 API",
                "requires_owner": not bool(baidu_token),
                "transport": "official_http_endpoint",
                "reason": "" if baidu_token and data.get("allow_baidu_http_submission") else ("需要站点API token" if not baidu_token else "已保存token；需确认允许调用百度官方HTTP提交端点"),
            },
            "bing": {
                "label": "Bing / IndexNow",
                "configured": bool(index_key),
                "ready": indexnow_ready,
                "mode": "IndexNow",
                "requires_owner": False,
                "initialization": indexnow_init,
                "reason": "" if indexnow_ready else (
                    deploy.get("reason") or
                    ("等待自动初始化并验证 IndexNow key 文件" if index_key else "公网部署就绪后会自动生成并验证 IndexNow key")
                ),
            },
            "google": {
                "label": "Google Search Console",
                "configured": bool(google_account and google_token),
                # A locally stored OAuth token is not proof that Google will
                # accept it.  Keep the connector visibly blocked after an
                # observed 401 instead of presenting a misleading green
                # "ready" state until the owner completes OAuth again.
                "ready": google_ready,
                "reauthorization_required": google_auth_error,
                "mode": "Search Console Sitemap API",
                "requires_owner": not google_ready,
                "account_id": google_account.get("account_id") if google_account else None,
                "reason": (
                    "最近一次 Google API 返回 401，OAuth 已失效；请点击“去官方授权”重新授权"
                    if google_auth_error else (
                        "" if google_ready else "需要通过统一账号中心完成 Google Search Console OAuth 授权"
                    )
                ),
            },
        },
        "ready_engines": [name for name, row in {
            "baidu": bool(baidu_token and data.get("allow_baidu_http_submission")),
            "bing": indexnow_ready,
            "google": google_ready,
        }.items() if row],
        "truth": "配置/授权只代表连接器可用；只有搜索平台返回可审计接收响应后，页面才进入 SUBMITTED。SUBMITTED 仍不等于 CRAWLED/INDEXED/RANKED。",
        "last_run_at": data.get("last_run_at") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
    }


def _google_oauth_reauthorization_required(last_result: dict) -> bool:
    """Return true only for a persisted, real Google OAuth rejection.

    This deliberately keys off the official response rather than a generic
    submit failure, so a temporary network error remains retryable and does
    not incorrectly ask the owner to repeat OAuth.
    """
    for failure in list(last_result.get("failed") or []):
        if failure.get("engine") != "google_search_console":
            continue
        result = failure.get("result") or {}
        status = str(result.get("status") or "")
        body = str(result.get("response") or "").upper()
        error = str(result.get("error") or "").upper()
        if status == "401" or "UNAUTHENTICATED" in body or "INVALID CREDENTIAL" in body or "INVALID CREDENTIAL" in error:
            return True
    return False


def submit_pending(limit: int = MAX_SUBMISSION_BATCH) -> dict:
    data = _load()
    data["last_run_at"] = now_iso()
    assets = _public_assets()
    if not assets:
        result = {"skipped": True, "reason": "no_verified_public_pages", "submitted": [], "failed": []}
        data["last_result"] = result
        _save(data)
        return result

    batch_limit = _batch_limit(limit)
    pending_by_engine = {}
    legacy_by_engine = {}
    baidu_quota_hold = _baidu_quota_held_today(data)
    for engine in ("indexnow", "google_search_console", "baidu"):
        pending_by_engine[engine], legacy_by_engine[engine] = _eligible_assets(data, engine, assets, batch_limit)
    if baidu_quota_hold:
        pending_by_engine["baidu"] = []

    if not any(pending_by_engine.values()):
        result = {
            "skipped": True,
            "reason": "no_new_or_updated_public_pages",
            "submitted": [],
            "failed": [],
            "batch_limit": batch_limit,
            "eligible_by_engine": {engine: 0 for engine in pending_by_engine},
            "legacy_public_assets_skipped": max(legacy_by_engine.values(), default=0),
            "baidu_quota_hold": baidu_quota_hold,
            "truth": "仅提交新发布或实质更新的页面版本；已在当天尝试过的页面不会重复提交。",
        }
        data["last_result"] = result
        _save(data)
        return result

    submitted: list[dict] = []
    failed: list[dict] = []
    site_url = _https_url(data.get("site_url"), "site_url")
    deploy = seo_public_deployer.status()

    # IndexNow / Bing: key can be generated locally and hosted inside /seo/, so no
    # external account login is required. The key file must itself be reachable first.
    initialization = initialize_indexnow()
    key = _indexnow_key()
    if initialization.get("ok") and key and deploy.get("ready"):
        verification = dict(initialization.get("verification") or {})
        pending = pending_by_engine["indexnow"]
        if verification.get("ok") and pending:
            _record_attempt(data, "indexnow", pending)
            receipt = _submit_indexnow([x["public_url"] for x in pending], key, verification["key_location"], str(data.get("indexnow_endpoint") or DEFAULT["indexnow_endpoint"]))
            receipt_id = f"INDEXNOW-{now_iso().replace(':','').replace('-','')}"
            _append_receipt({"receipt_id": receipt_id, "engine": "indexnow", "result": receipt, "key_location": verification.get("key_location"), "created_at": now_iso()})
            if receipt.get("ok"):
                for asset in pending:
                    _record_submission(asset, "indexnow", receipt_id)
                    submitted.append({"asset_id": asset["id"], "engine": "indexnow", "receipt": receipt_id})
            else:
                failed.append({"engine": "indexnow", "reason": "endpoint_rejected", "result": receipt})
        elif pending:
            failed.append({"engine": "indexnow", "reason": "key_file_public_verification_failed", "verification": verification})
    elif deploy.get("ready"):
        failed.append({"engine": "indexnow", "reason": initialization.get("reason") or "indexnow_initialization_failed", "initialization": initialization})

    # Google Search Console: submit the verified /seo/sitemap.xml through the
    # OAuth account already held by the unified account center.
    google_account = _connected_account("google_search_console")
    google_token = _google_access_token(google_account)
    google_pending = pending_by_engine["google_search_console"]
    if google_account and google_token and google_pending:
        _record_attempt(data, "google_search_console", google_pending)
        sitemap_url = urllib.parse.urljoin(site_url, "seo/sitemap.xml")
        g_result = _submit_google_sitemap(str(data.get("google_site_url") or site_url), sitemap_url, google_token)
        receipt_id = f"GSC-{now_iso().replace(':','').replace('-','')}"
        _append_receipt({"receipt_id": receipt_id, "engine": "google_search_console", "result": g_result, "created_at": now_iso()})
        if g_result.get("ok"):
            for asset in google_pending:
                _record_submission(asset, "google_search_console", receipt_id)
                submitted.append({"asset_id": asset["id"], "engine": "google_search_console", "receipt": receipt_id})
        else:
            failed.append({"engine": "google_search_console", "reason": "sitemap_submit_failed", "result": g_result})

    # Baidu: the official ordinary-indexing API is documented as HTTP. Keep it
    # disabled until the owner explicitly opts in after supplying the verified
    # site's token; never expose the token in returned status/results.
    baidu_token = _baidu_token()
    baidu_pending = pending_by_engine["baidu"]
    if baidu_token and data.get("allow_baidu_http_submission") and baidu_pending:
        _record_attempt(data, "baidu", baidu_pending)
        b_result = _submit_baidu([x["public_url"] for x in baidu_pending], str(data.get("baidu_site") or "kazuizhi.com"), baidu_token)
        receipt_id = f"BAIDU-{now_iso().replace(':','').replace('-','')}"
        _append_receipt({"receipt_id": receipt_id, "engine": "baidu", "result": b_result, "created_at": now_iso()})
        if b_result.get("ok"):
            for asset in baidu_pending:
                _record_submission(asset, "baidu", receipt_id)
                submitted.append({"asset_id": asset["id"], "engine": "baidu", "receipt": receipt_id})
        else:
            failed.append({
                "engine": "baidu",
                "reason": "baidu_quota_exhausted" if _baidu_quota_exhausted(b_result) else "api_submit_failed",
                "result": b_result,
            })

    result = {
        "skipped": False,
        "attempted_public_assets": max((len(rows) for rows in pending_by_engine.values()), default=0),
        "batch_limit": batch_limit,
        "eligible_by_engine": {engine: len(rows) for engine, rows in pending_by_engine.items()},
        "legacy_public_assets_skipped": max(legacy_by_engine.values(), default=0),
        "baidu_quota_hold": baidu_quota_hold,
        "submitted": submitted,
        "submitted_count": len(submitted),
        "failed": failed,
        "failed_count": len(failed),
        "indexnow_initialization": initialization,
        "truth": "每次最多提交 3 个新发布或实质更新的页面版本；同一页面版本当天只尝试一次。搜索平台接收回执只推进到 SUBMITTED；抓取、收录、排名和AI引用必须继续等待真实外部证据。",
    }
    data["last_result"] = result
    _save(data)
    return result
