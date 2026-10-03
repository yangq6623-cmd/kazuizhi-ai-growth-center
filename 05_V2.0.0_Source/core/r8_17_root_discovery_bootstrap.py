"""Server-local, least-privilege repair for missing root discovery files.

This helper is intentionally separate from the desktop Remote Agent.  It is
run by an administrator *on the IIS server* and can create only robots.txt and
sitemap.xml at the configured site root.  It never overwrites an existing
local file and requires a public HTTP 404 before attempting a creation.
"""
from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_SITE_ROOT = r"C:\\inetpub\\kazuizhi"
DEFAULT_PUBLIC_BASE_URL = "https://kazuizhi.com/"
_ALLOWED_ROOT_FILES = ("robots.txt", "sitemap.xml")


def _files(public_base_url: str) -> dict[str, bytes]:
    base = urllib.parse.urljoin(str(public_base_url or "").strip() + "/", "./")
    root_sitemap = urllib.parse.urljoin(base, "sitemap.xml")
    seo_sitemap = urllib.parse.urljoin(base, "seo/sitemap.xml")
    robots = f"User-agent: *\\nAllow: /\\nSitemap: {root_sitemap}\\nSitemap: {seo_sitemap}\\n"
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n'
        f"  <sitemap><loc>{seo_sitemap}</loc></sitemap>\\n"
        "</sitemapindex>\\n"
    )
    return {"robots.txt": robots.encode("utf-8"), "sitemap.xml": sitemap.encode("utf-8")}


def _http_status(url: str, timeout: int = 12) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Kazuizhi-R8-17-RootDiscovery/1.0"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - operator supplied HTTPS public base
            return {"ok": True, "status": int(getattr(response, "status", 200) or 200), "url": url}
    except urllib.error.HTTPError as error:
        return {"ok": False, "status": int(error.code), "url": url}
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "status": None, "url": url, "error": str(error)[:300]}


def _safe_site_root(value: str) -> Path:
    root = Path(str(value or "")).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("site_root 不存在或不是目录")
    return root


def _write_new_file(path: Path, content: bytes) -> None:
    """Atomically create a new file and refuse to replace an existing one."""
    if path.exists():
        raise FileExistsError(f"existing file preserved: {path.name}")
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # os.link refuses to replace a pre-existing destination. This prevents
        # a race from turning the repair into an overwrite.
        os.link(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def execute(
    site_root: str = DEFAULT_SITE_ROOT,
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL,
    *,
    fetch_status=_http_status,
) -> dict:
    """Create only genuinely missing root discovery files, then recheck them."""
    root = _safe_site_root(site_root)
    base = urllib.parse.urljoin(str(public_base_url or "").strip() + "/", "./")
    if not base.startswith("https://"):
        raise ValueError("public_base_url 必须为 HTTPS 地址")

    results = {}
    for relative, content in _files(base).items():
        if relative not in _ALLOWED_ROOT_FILES:
            raise ValueError("不允许的根目录文件")
        target = (root / relative).resolve()
        if target.parent != root:
            raise ValueError("根目录写入路径不安全")
        public_url = urllib.parse.urljoin(base, relative)
        before = fetch_status(public_url)
        item = {"before": before, "created": False, "preserved": False, "after": None, "error": ""}
        if before.get("status") == 404:
            if target.exists():
                item["preserved"] = True
                item["reason"] = "local_file_exists_public_404_preserved"
            else:
                try:
                    _write_new_file(target, content)
                    item["created"] = True
                    item["after"] = fetch_status(public_url)
                except (OSError, ValueError) as error:
                    item["error"] = str(error)
        elif before.get("status") is None:
            item["preserved"] = True
            item["reason"] = "public_check_unavailable_preserved"
        else:
            item["preserved"] = True
            item["reason"] = "public_file_already_exists_preserved"
        results[relative] = item

    verified = all(
        ((row.get("after") or {}).get("status") == 200)
        or ((row.get("before") or {}).get("status") == 200)
        for row in results.values()
    )
    return {
        "schema": "kz.r8-17-root-discovery-bootstrap.v1",
        "site_root": str(root),
        "public_base_url": base,
        "files": results,
        "verified": verified,
        "exit_code": 0 if verified else 4,
        "truth": "仅当公网为 HTTP 404 且服务器本地文件不存在时创建 robots.txt / sitemap.xml；已有文件不覆盖。只有公网 HTTP 200 才算验证完成。",
    }
