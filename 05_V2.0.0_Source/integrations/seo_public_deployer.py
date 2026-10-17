"""R8-15 guarded public SEO page deployment connector.

The connector is deliberately narrow:
- it only writes below <site_root>/seo/
- it never overwrites Web.config, App_Data, uploads, APKs, databases or other site roots
- it uses atomic file replacement
- a page is marked PUBLISHED only after its public URL returns HTTP 2xx and passes
  content, canonical, Schema and robots/indexability verification
- missing configuration is a human setup item, not a fake deployment failure

The deployment target is intentionally configured at runtime. No server password,
GitHub token or platform secret is stored here.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
import urllib.robotparser
from copy import deepcopy
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core.storage import now_iso, read_json, write_json
from core.seo_geo_growth import dashboard, record_asset_stage

STORE = "r8_15/seo_public_deploy.json"
RECEIPTS = "r8_15/seo_public_deploy_receipts.json"
SCHEMA = "kz.seo-public-deploy.v1"
DEFAULT = {
    "schema": SCHEMA,
    "enabled": False,
    "mode": "local_iis_filesystem",
    "site_root": "",
    "public_base_url": "https://kazuizhi.com/",
    "managed_subdir": "seo",
    "verify_http": True,
    "verify_timeout_seconds": 8,
    "updated_at": "",
    "last_run_at": "",
    "last_result": {},
}


def _load():
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    for key, value in DEFAULT.items():
        data.setdefault(key, deepcopy(value))
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _safe_root(value: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("site_root 不能为空")
    root = Path(raw).expanduser()
    if not root.is_absolute():
        raise ValueError("site_root 必须是绝对路径")
    resolved = root.resolve()
    # Never accept filesystem/drive roots. The connector may only work in a
    # specific website directory, and later only inside its /seo child.
    if resolved == Path(resolved.anchor):
        raise ValueError("禁止把磁盘根目录作为网站部署目录")
    return resolved


def _safe_public_base(value: str) -> str:
    url = str(value or "").strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError("public_base_url 必须是有效 HTTPS 公网地址")
    return url.rstrip("/") + "/"


def configure(payload: dict) -> dict:
    data = _load()
    if "site_root" in payload:
        data["site_root"] = str(_safe_root(payload.get("site_root")))
    if "public_base_url" in payload:
        data["public_base_url"] = _safe_public_base(payload.get("public_base_url"))
    if "enabled" in payload:
        data["enabled"] = bool(payload.get("enabled"))
    if "verify_http" in payload:
        data["verify_http"] = bool(payload.get("verify_http"))
    if "verify_timeout_seconds" in payload:
        data["verify_timeout_seconds"] = max(3, min(20, int(payload.get("verify_timeout_seconds") or 8)))
    _save(data)
    return status()


def _target_dir(data: dict) -> Path | None:
    try:
        root = _safe_root(data.get("site_root"))
    except ValueError:
        return None
    return root / "seo"


def status() -> dict:
    data = _load()
    target = _target_dir(data)
    root = None
    exists = False
    writable = False
    if target is not None:
        root = target.parent
        exists = root.exists() and root.is_dir()
        if exists:
            try:
                probe_dir = target if target.exists() else root
                writable = os.access(probe_dir, os.W_OK)
            except OSError:
                writable = False
    ready = bool(data.get("enabled") and exists and writable)
    reason = ""
    if not data.get("enabled"):
        reason = "公网部署连接器未启用"
    elif target is None:
        reason = "尚未配置网站绝对目录"
    elif not exists:
        reason = "配置的网站目录在当前机器不可见"
    elif not writable:
        reason = "当前运行账户对网站目录没有写权限"
    return {
        "configured": bool(data.get("site_root")),
        "enabled": bool(data.get("enabled")),
        "ready": ready,
        "mode": data.get("mode"),
        "site_root": str(root) if root else "",
        "managed_subdir": "seo",
        "public_base_url": data.get("public_base_url"),
        "verify_http": bool(data.get("verify_http")),
        "reason": reason,
        "last_run_at": data.get("last_run_at") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
        "safety": {
            "writes_only_below": "<site_root>/seo/",
            "touches_web_config": False,
            "touches_app_data": False,
            "touches_uploads": False,
            "touches_database": False,
            "atomic_replace": True,
            "public_http_verification_required": bool(data.get("verify_http")),
            "canonical_verification_required": True,
            "schema_verification_required": True,
            "robots_verification_required": True,
        },
        "truth": "写入文件不等于已公开；只有公网URL真实返回2xx，并通过内容、canonical、Schema、robots/indexability校验后才记录 PUBLISHED。",
    }


def _atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".kz-seo-", suffix=".tmp", dir=str(destination.parent))
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        shutil.copyfile(source, tmp)
        os.replace(tmp, destination)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _normalize_compare_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    host = parts.netloc.lower()
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") + "/"
    return f"{scheme}://{host}{path}"


def _tag_attributes(tag: str) -> dict:
    return {
        key.lower(): value.strip()
        for key, _quote, value in re.findall(r"([:\w-]+)\s*=\s*([\"'])(.*?)\2", tag, flags=re.I | re.S)
    }


def _inspect_public_html(body: str, expected: str, expected_canonical: str) -> dict:
    content_match = bool(not expected or expected in body)

    canonical = ""
    for tag in re.findall(r"<link\b[^>]*>", body, flags=re.I | re.S):
        attrs = _tag_attributes(tag)
        rel_tokens = {token.strip().lower() for token in attrs.get("rel", "").split()}
        if "canonical" in rel_tokens:
            canonical = attrs.get("href", "").strip()
            break
    canonical_match = bool(
        canonical
        and expected_canonical
        and _normalize_compare_url(canonical) == _normalize_compare_url(expected_canonical)
    )

    schema_valid = False
    schema_types = []
    for match in re.finditer(
        r"<script\b[^>]*type\s*=\s*([\"'])application/ld\+json\1[^>]*>(.*?)</script>",
        body,
        flags=re.I | re.S,
    ):
        try:
            payload = json.loads(match.group(2).strip())
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, (dict, list)):
            schema_valid = True
            if isinstance(payload, dict):
                graph = payload.get("@graph") if isinstance(payload.get("@graph"), list) else [payload]
                schema_types.extend(str(item.get("@type")) for item in graph if isinstance(item, dict) and item.get("@type"))
            break

    noindex = False
    for tag in re.findall(r"<meta\b[^>]*>", body, flags=re.I | re.S):
        attrs = _tag_attributes(tag)
        if attrs.get("name", "").lower() in {"robots", "googlebot", "bingbot", "baiduspider"}:
            directives = {part.strip().lower() for part in attrs.get("content", "").split(",")}
            if "noindex" in directives or "none" in directives:
                noindex = True
                break

    return {
        "content_match": content_match,
        "canonical": canonical,
        "canonical_match": canonical_match,
        "schema_valid": schema_valid,
        "schema_types": schema_types,
        "page_indexable": not noindex,
    }


def _verify_robots(url: str, timeout: int) -> dict:
    robots_url = urljoin(url, "/robots.txt")
    request = urllib.request.Request(
        robots_url,
        headers={"User-Agent": "Kazuizhi-R8-15-Public-Deploy-Verifier/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = int(getattr(response, "status", 200) or 200)
            body = response.read(256 * 1024).decode("utf-8", errors="replace")
            if not 200 <= code < 300:
                return {"ok": False, "allowed": False, "status": code, "url": robots_url}
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(body.splitlines())
            allowed = bool(parser.can_fetch("*", url))
            return {"ok": allowed, "allowed": allowed, "status": code, "url": robots_url}
    except urllib.error.HTTPError as error:
        # A missing robots.txt means there is no robots rule blocking /seo/.
        if int(getattr(error, "code", 0) or 0) == 404:
            return {"ok": True, "allowed": True, "status": 404, "url": robots_url, "reason": "robots_not_present"}
        return {"ok": False, "allowed": False, "status": int(getattr(error, "code", 0) or 0), "url": robots_url, "error": str(error)}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "allowed": False, "url": robots_url, "error": str(error)}


def _verify_public_url(url: str, expected: str, expected_canonical: str, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Kazuizhi-R8-15-Public-Deploy-Verifier/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = int(getattr(response, "status", 200) or 200)
            body = response.read(512 * 1024).decode("utf-8", errors="replace")
            page = _inspect_public_html(body, expected, expected_canonical)
            robots = _verify_robots(url, timeout)
            ok = bool(
                200 <= code < 300
                and page["content_match"]
                and page["canonical_match"]
                and page["schema_valid"]
                and page["page_indexable"]
                and robots.get("allowed")
            )
            return {
                "ok": ok,
                "status": code,
                **page,
                "robots": robots,
                "checked_at": now_iso(),
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "checked_at": now_iso()}


def _append_receipt(receipt: dict) -> None:
    data = read_json(RECEIPTS, {"schema": "kz.seo-public-deploy-receipts.v1", "items": []})
    if not isinstance(data, dict):
        data = {"schema": "kz.seo-public-deploy-receipts.v1", "items": []}
    data.setdefault("items", []).insert(0, receipt)
    data["items"] = data["items"][:500]
    data["updated_at"] = now_iso()
    write_json(RECEIPTS, data)


def _write_managed_sitemap(target: Path) -> str:
    snap = dashboard()
    urls = sorted({
        str(asset.get("public_url") or "").strip()
        for asset in snap.get("assets", [])
        if str(asset.get("public_url") or "").startswith(("http://", "https://"))
    })
    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    xml += "\n".join(f"  <url><loc>{url}</loc></url>" for url in urls)
    xml += "\n</urlset>\n"
    path = target / "sitemap.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return str(path)


def deploy_pending(limit: int = 10) -> dict:
    data = _load()
    state = status()
    data["last_run_at"] = now_iso()
    if not state.get("ready"):
        result = {"skipped": True, "reason": state.get("reason") or "deploy_connector_not_ready", "published": [], "failed": []}
        data["last_result"] = result
        _save(data)
        return result

    target = _target_dir(data)
    assert target is not None
    base = _safe_public_base(data.get("public_base_url"))
    snap = dashboard()
    pending = [x for x in snap.get("assets", []) if x.get("stage") == "QC_PASSED"][: max(0, int(limit))]
    published = []
    failed = []
    timeout = int(data.get("verify_timeout_seconds") or 8)

    for asset in pending:
        asset_id = str(asset.get("id") or "")
        slug = str(asset.get("slug") or "").strip()
        source = Path(str(asset.get("staging_path") or ""))
        if not asset_id or not slug or "/" in slug or "\\" in slug or not source.is_file():
            failed.append({"asset_id": asset_id, "reason": "invalid_asset_or_staging_file"})
            continue
        destination = target / slug / "index.html"
        try:
            _atomic_copy(source, destination)
            public_url = urljoin(base, f"seo/{slug}/")
            expected_canonical = str(asset.get("canonical") or public_url)
            verification = (
                _verify_public_url(public_url, str(asset.get("title") or ""), expected_canonical, timeout)
                if data.get("verify_http")
                else {"ok": False, "reason": "http_verification_disabled", "checked_at": now_iso()}
            )
            receipt = {
                "receipt_id": f"DEPLOY-{asset_id}-{now_iso().replace(':','').replace('-','')}",
                "asset_id": asset_id,
                "destination": str(destination),
                "public_url": public_url,
                "verification": verification,
                "created_at": now_iso(),
            }
            _append_receipt(receipt)
            if not verification.get("ok"):
                failed.append({"asset_id": asset_id, "reason": "public_http_verification_failed", "public_url": public_url, "verification": verification})
                continue
            record_asset_stage(asset_id, "PUBLISHED", {
                "public_url": public_url,
                "connector": "r8_15_local_iis_filesystem",
                "deploy_receipt": receipt["receipt_id"],
                "http_verification": verification,
            })
            published.append({"asset_id": asset_id, "public_url": public_url, "receipt": receipt["receipt_id"]})
        except (OSError, ValueError, RuntimeError) as error:
            failed.append({"asset_id": asset_id, "reason": str(error)})

    sitemap_path = _write_managed_sitemap(target)
    result = {
        "skipped": False,
        "attempted": len(pending),
        "published": published,
        "failed": failed,
        "managed_sitemap": sitemap_path,
        "truth": "只有已通过公网HTTP、内容、canonical、Schema、robots/indexability验证的页面才进入 PUBLISHED；仅写入服务器文件不计成功。",
    }
    data["last_result"] = result
    _save(data)
    return result
