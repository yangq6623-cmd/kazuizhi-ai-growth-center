"""R8-17: route guarded public deployment through the server Remote Agent.

This patch keeps R8-15 local-IIS mode for backwards compatibility, while adding
a remote_agent_v1 mode for the normal desktop architecture.  A server write is
never enough to claim PUBLISHED: the existing R8-15 public HTTP/content/
canonical/Schema/robots verification still has to pass afterward.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import html
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from core.storage import now_iso
from integrations import remote_agent
from integrations import seo_public_deployer as deployer

REMOTE_MODE = "remote_agent_v1"
_ORIGINAL_CONFIGURE = deployer.configure
_ORIGINAL_STATUS = deployer.status
_ORIGINAL_DEPLOY_PENDING = deployer.deploy_pending
_INSTALLED = False


def _remote_mode() -> bool:
    try:
        return str(deployer._load().get("mode") or "").strip() == REMOTE_MODE
    except (OSError, ValueError, RuntimeError, TypeError):
        return False


def activate_remote_mode_if_ready(*, check_live: bool = True) -> dict:
    agent = remote_agent.status(check_live=check_live)
    if not agent.get("configured"):
        return {"ok": False, "activated": False, "reason": "remote_agent_not_paired"}
    if check_live and not agent.get("connected"):
        return {"ok": False, "activated": False, "reason": agent.get("last_error") or "remote_agent_offline"}
    data = deployer._load()
    data["mode"] = REMOTE_MODE
    data["enabled"] = True
    data["site_root"] = ""
    data["public_base_url"] = deployer._safe_public_base(data.get("public_base_url") or "https://kazuizhi.com/")
    deployer._save(data)
    return {"ok": True, "activated": True, "mode": REMOTE_MODE, "remote_agent": agent}


def configure(payload: dict) -> dict:
    requested = str((payload or {}).get("mode") or "").strip()
    if requested != REMOTE_MODE:
        return _ORIGINAL_CONFIGURE(payload)
    agent = remote_agent.status(check_live=True)
    if not agent.get("configured"):
        raise ValueError("请先导入 R8-17 Remote Agent 配对文件")
    data = deployer._load()
    data["mode"] = REMOTE_MODE
    data["enabled"] = bool(payload.get("enabled", True))
    if "public_base_url" in payload:
        data["public_base_url"] = deployer._safe_public_base(payload.get("public_base_url"))
    else:
        data["public_base_url"] = deployer._safe_public_base(data.get("public_base_url") or "https://kazuizhi.com/")
    if "verify_http" in payload:
        data["verify_http"] = bool(payload.get("verify_http"))
    data["site_root"] = ""
    deployer._save(data)
    return status()


def status() -> dict:
    if not _remote_mode():
        local = _ORIGINAL_STATUS()
        local.setdefault("mode", "local_iis_filesystem")
        return local
    data = deployer._load()
    agent = remote_agent.status(check_live=True)
    configured = bool(agent.get("configured"))
    connected = bool(agent.get("connected"))
    enabled = bool(data.get("enabled"))
    ready = bool(enabled and connected and agent.get("website_ready"))
    reason = ""
    if not enabled:
        reason = "远程公网发布连接器未启用"
    elif not configured:
        reason = "请把服务器 Pairing JSON 复制到本机桌面后重新启动卡嘴子 AI"
    elif not connected:
        reason = agent.get("last_error") or "Remote Agent 当前不可达"
    elif not agent.get("website_ready"):
        reason = "Remote Agent 报告生产网站目录未就绪"
    return {
        "configured": configured,
        "enabled": enabled,
        "ready": ready,
        "mode": REMOTE_MODE,
        "site_root": "",
        "managed_subdir": "seo",
        "public_base_url": data.get("public_base_url"),
        "verify_http": bool(data.get("verify_http")),
        "reason": reason,
        "remote_agent": {
            "connected": connected,
            "version": agent.get("version"),
            "endpoint": agent.get("endpoint"),
            "last_health_at": agent.get("last_health_at"),
            "secret_exposed": False,
        },
        "last_run_at": data.get("last_run_at") or "",
        "last_result": data.get("last_result") or {},
        "safety": "桌面AI仅可通过 Remote Agent 写 seo/downloads/apk/public 等白名单静态目录；PUBLISHED 仍必须通过真实公网验证。",
    }


def _job_id(asset_id: str, prefix: str = "SEO") -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(asset_id or ""))[:56]
    stamp = now_iso().replace(":", "").replace("-", "").replace("+", "-")
    return f"{prefix}-{safe or 'ASSET'}-{stamp}"[:96]


def _sitemap_xml() -> bytes:
    snap = deployer.dashboard()
    rows = sorted(
        [asset for asset in snap.get("assets", []) if str(asset.get("public_url") or "").startswith("https://")],
        key=lambda asset: str(asset.get("public_url") or ""),
    )
    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    xml += "\n".join(
        f"  <url><loc>{html.escape(str(asset.get('public_url') or ''), quote=True)}</loc><lastmod>{str(asset.get('updated_at') or asset.get('published_at') or now_iso())[:10]}</lastmod></url>"
        for asset in rows
    )
    xml += "\n</urlset>\n"
    return xml.encode("utf-8")


def _root_discovery_files(base: str) -> dict:
    """Return safe root discovery files for the managed /seo/ sitemap.

    The Remote Agent permits these two root files only.  They are created only
    after a real HTTP 404 check, so an existing site-owned robots.txt or
    sitemap.xml is never overwritten by the desktop agent.
    """
    sitemap_url = urllib.parse.urljoin(base, "seo/sitemap.xml")
    root_sitemap_url = urllib.parse.urljoin(base, "sitemap.xml")
    robots = "User-agent: *\nAllow: /\nSitemap: " + root_sitemap_url + "\nSitemap: " + sitemap_url + "\n"
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <sitemap><loc>{sitemap_url}</loc></sitemap>\n"
        "</sitemapindex>\n"
    )
    return {"robots.txt": robots.encode("utf-8"), "sitemap.xml": sitemap.encode("utf-8")}


def _public_status(url: str, timeout: int) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-17-Discovery/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - validated production base
            return {"ok": True, "status": int(getattr(response, "status", 200) or 200), "url": url}
    except urllib.error.HTTPError as error:
        return {"ok": False, "status": int(error.code), "url": url}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": None, "url": url, "error": str(error)[:300]}


def _public_text(url: str, timeout: int) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-25-DiscoveryRepair/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - validated production base
            body = response.read(512 * 1024)
            return {
                "ok": True,
                "status": int(getattr(response, "status", 200) or 200),
                "url": url,
                "body": body,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        return {"ok": False, "status": int(getattr(error, "code", 0) or 0) or None, "url": url, "error": str(error)[:300]}


def _legacy_root_sitemap(body: bytes, base: str) -> bool:
    """Recognize only the exact malformed root sitemap emitted by old builds."""
    try:
        root = ET.fromstring(bytes(body or b"").decode("utf-8", errors="replace"))
    except (ET.ParseError, ValueError, TypeError):
        return False
    if root.tag.rsplit("}", 1)[-1] != "urlset":
        return False
    urls = {
        str(node.text or "").strip().rstrip("/") + "/"
        for node in root.iter()
        if node.tag.rsplit("}", 1)[-1] == "loc" and str(node.text or "").strip()
    }
    expected = {
        urllib.parse.urljoin(base, "").rstrip("/") + "/",
        urllib.parse.urljoin(base, "seo/sitemap.xml").rstrip("/") + "/",
    }
    return urls == expected


def _ensure_root_discovery(base: str, timeout: int) -> dict:
    """Create missing root discovery files without touching existing files."""
    files = _root_discovery_files(base)
    results = {}
    for relative, content in files.items():
        public_url = urllib.parse.urljoin(base, relative)
        before = _public_status(public_url, timeout)
        result = {"before": before, "created": False, "receipt": None, "after": None}
        if before.get("status") == 404:
            try:
                receipt = remote_agent.upload_bytes(relative, content, job_id=_job_id("ROOT-" + relative, "DISCOVERY"))
                result["created"] = True
                result["receipt"] = receipt
                result["after"] = _public_status(public_url, timeout)
            except (OSError, ValueError, RuntimeError) as error:
                result["error"] = str(error)
        elif before.get("status") is None:
            result["reason"] = "root_http_check_unavailable_existing_file_preserved"
        elif relative == "sitemap.xml" and before.get("status") == 200:
            current = _public_text(public_url, timeout)
            if current.get("ok") and _legacy_root_sitemap(current.get("body") or b"", base):
                try:
                    previous = bytes(current.get("body") or b"")
                    receipt = remote_agent.upload_bytes(relative, content, job_id=_job_id("ROOT-SITEMAP-REPAIR", "DISCOVERY"))
                    result["repaired"] = True
                    result["receipt"] = receipt
                    result["previous_sha256"] = current.get("sha256")
                    result["previous_body"] = previous.decode("utf-8", errors="replace")
                    result["after"] = _public_text(public_url, timeout)
                    after_body = bytes((result["after"] or {}).get("body") or b"")
                    result["repair_verified"] = bool(
                        (result["after"] or {}).get("status") == 200
                        and b"<sitemapindex" in after_body
                        and urllib.parse.urljoin(base, "seo/sitemap.xml").encode("utf-8") in after_body
                    )
                    if isinstance(result.get("after"), dict):
                        result["after"].pop("body", None)
                except (OSError, ValueError, RuntimeError) as error:
                    result["error"] = str(error)
            else:
                result["reason"] = "root_file_already_exists_preserved"
        else:
            result["reason"] = "root_file_already_exists_preserved"
        results[relative] = result
    return {
        "root_robots_url": urllib.parse.urljoin(base, "robots.txt"),
        "root_sitemap_url": urllib.parse.urljoin(base, "sitemap.xml"),
        "managed_seo_sitemap_url": urllib.parse.urljoin(base, "seo/sitemap.xml"),
        "files": results,
        "truth": "根目录文件仅在真实 HTTP 404 时创建；只有精确匹配旧版错误模板的 sitemap.xml 才会保留原文与SHA256后修复，其他已有文件保持不变。创建或修复后仍需真实公网 HTTP 回查。",
    }


def deploy_pending(limit: int = 10) -> dict:
    if not _remote_mode():
        return _ORIGINAL_DEPLOY_PENDING(limit=limit)
    data = deployer._load()
    state = status()
    data["last_run_at"] = now_iso()
    if not state.get("ready"):
        result = {"skipped": True, "reason": state.get("reason") or "remote_agent_not_ready", "published": [], "failed": []}
        data["last_result"] = result
        deployer._save(data)
        return result

    base = deployer._safe_public_base(data.get("public_base_url"))
    snap = deployer.dashboard()
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
        relative = f"seo/{slug}/index.html"
        public_url = urllib.parse.urljoin(base, f"seo/{slug}/")
        try:
            remote_receipt = remote_agent.upload_file(relative, source, job_id=_job_id(asset_id))
            expected_canonical = str(asset.get("canonical") or public_url)
            verification = (
                deployer._verify_public_url(public_url, str(asset.get("title") or ""), expected_canonical, timeout)
                if data.get("verify_http")
                else {"ok": False, "reason": "http_verification_disabled", "checked_at": now_iso()}
            )
            receipt = {
                "receipt_id": f"REMOTE-DEPLOY-{asset_id}-{now_iso().replace(':','').replace('-','')}",
                "asset_id": asset_id,
                "connector": REMOTE_MODE,
                "remote_job_id": remote_receipt.get("job_id"),
                "remote_sha256": remote_receipt.get("sha256"),
                "destination": relative,
                "public_url": public_url,
                "verification": verification,
                "created_at": now_iso(),
            }
            deployer._append_receipt(receipt)
            if not verification.get("ok"):
                failed.append({"asset_id": asset_id, "reason": "public_http_verification_failed", "public_url": public_url, "verification": verification})
                continue
            deployer.record_asset_stage(asset_id, "PUBLISHED", {
                "public_url": public_url,
                "connector": REMOTE_MODE,
                "deploy_receipt": receipt["receipt_id"],
                "remote_job_id": remote_receipt.get("job_id"),
                "http_verification": verification,
            })
            published.append({"asset_id": asset_id, "public_url": public_url, "receipt": receipt["receipt_id"]})
        except (OSError, ValueError, RuntimeError) as error:
            failed.append({"asset_id": asset_id, "reason": str(error)})

    sitemap_result = {}
    try:
        sitemap_result = remote_agent.upload_bytes("seo/sitemap.xml", _sitemap_xml(), job_id=_job_id("SITEMAP", "SITEMAP"))
    except (OSError, ValueError, RuntimeError) as error:
        sitemap_result = {"ok": False, "error": str(error)}
    root_discovery = _ensure_root_discovery(base, timeout)

    result = {
        "skipped": False,
        "attempted": len(pending),
        "published": published,
        "failed": failed,
        "managed_sitemap": "https://kazuizhi.com/seo/sitemap.xml",
        "sitemap_remote_receipt": sitemap_result,
        "root_discovery": root_discovery,
        "truth": "Remote Agent 写入不等于发布成功；只有公网HTTP、内容、canonical、Schema、robots/indexability全部验证通过才进入 PUBLISHED。",
    }
    data["last_result"] = result
    deployer._save(data)
    return result


def _patch_indexnow_key_hosting() -> None:
    from integrations import search_engine_submitter as searcher

    original = searcher._ensure_indexnow_key_file

    def ensure_key(key: str, timeout: int = 8) -> dict:
        deploy = status()
        if deploy.get("mode") != REMOTE_MODE:
            return original(key, timeout=timeout)
        if not deploy.get("ready"):
            return {"ok": False, "reason": deploy.get("reason") or "remote_agent_not_ready"}
        try:
            receipt = remote_agent.upload_bytes(f"seo/{key}.txt", key.encode("utf-8"), job_id=_job_id("INDEXNOW", "INDEXNOW"))
        except (OSError, ValueError, RuntimeError) as error:
            return {"ok": False, "reason": "remote_key_publish_failed", "error": str(error), "checked_at": now_iso()}
        base = str(deploy.get("public_base_url") or "https://kazuizhi.com/").rstrip("/") + "/"
        public_url = urllib.parse.urljoin(base, f"seo/{key}.txt")
        request = urllib.request.Request(public_url, headers={"User-Agent": "Kazuizhi-R8-17-IndexNow/1.0"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - URL derives from validated production HTTPS base
                code = int(getattr(response, "status", 200) or 200)
                body = response.read(4096).decode("utf-8", errors="replace").strip()
            ok = 200 <= code < 300 and body == key
            return {"ok": ok, "status": code, "key_location": public_url, "remote_job_id": receipt.get("job_id"), "checked_at": now_iso()}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
            return {"ok": False, "error": str(error), "key_location": public_url, "checked_at": now_iso()}

    searcher._ensure_indexnow_key_file = ensure_key


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    deployer.configure = configure
    deployer.status = status
    deployer.deploy_pending = deploy_pending
    _patch_indexnow_key_hosting()
    _INSTALLED = True


install()
