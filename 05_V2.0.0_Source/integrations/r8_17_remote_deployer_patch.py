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
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from core.storage import now_iso
from core import seo_geo_growth
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


def _seo_hub_html(base: str) -> bytes:
    """Build a crawlable, managed entrypoint without overwriting the SPA home."""
    base = deployer._safe_public_base(base)
    hub_url = urllib.parse.urljoin(base, "seo/")
    rows = sorted(
        [asset for asset in deployer.dashboard().get("assets", []) if str(asset.get("public_url") or "").startswith("https://")],
        key=lambda asset: (str(asset.get("region") or ""), str(asset.get("service") or ""), str(asset.get("title") or "")),
    )
    links = "\n".join(
        f'<li><a href="{html.escape(str(asset.get("public_url") or ""), quote=True)}">{html.escape(str(asset.get("title") or asset.get("keyword") or "本地服务"))}</a><p>{html.escape(str(asset.get("description") or "查看公开服务说明与真实业务入口。"))}</p></li>'
        for asset in rows
    )
    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": base + "#organization", "name": "卡嘴子", "url": base},
            {"@type": "CollectionPage", "@id": hub_url + "#page", "url": hub_url,
             "name": "卡嘴子本地服务与维修指南", "isPartOf": {"@id": base + "#organization"},
             "mainEntity": [{"@type": "WebPage", "url": str(asset.get("public_url") or ""), "name": str(asset.get("title") or "")} for asset in rows]},
        ],
    }
    body = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow,max-image-preview:large"><title>卡嘴子本地服务与维修指南｜涟水、淮安</title><meta name="description" content="卡嘴子公开整理涟水、淮安水电维修、家电维修、管道疏通、安装服务与个人任务指南，提供可抓取的服务说明和正式需求入口。"><link rel="canonical" href="{html.escape(hub_url, quote=True)}"><meta property="og:type" content="website"><meta property="og:site_name" content="卡嘴子"><meta property="og:title" content="卡嘴子本地服务与维修指南"><meta property="og:description" content="查看公开服务范围、需求准备事项、售后流程和正式需求入口。"><meta property="og:url" content="{html.escape(hub_url, quote=True)}"><script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, separators=(',', ':'))}</script><style>body{{margin:0;background:#f5f8fc;color:#172033;font:16px/1.7 system-ui,-apple-system,"Microsoft YaHei",sans-serif}}main{{max-width:980px;margin:auto;padding:28px}}header,section{{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:26px;margin-bottom:18px}}h1{{font-size:32px;line-height:1.3}}ul{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:0;list-style:none}}li{{border:1px solid #e5eaf1;border-radius:12px;padding:16px}}li p{{color:#52657d}}a{{color:#175cd3}}.cta{{display:inline-block;background:#2878ff;color:#fff;text-decoration:none;padding:11px 18px;border-radius:10px;font-weight:700}}@media(max-width:720px){{main{{padding:12px}}ul{{grid-template-columns:1fr}}}}</style></head><body><main><header><p>卡嘴子公开服务资料库</p><h1>涟水、淮安本地服务与维修指南</h1><p>这里集中展示卡嘴子已经公开验证的服务说明页面。用户可了解服务范围、需求准备事项、检测报价原则、完工确认与售后留痕方式。页面只呈现可核验的公开规则，不虚构固定价格、案例、排名、搜索收录或AI推荐。</p><a class="cta" href="{html.escape(urllib.parse.urljoin(base, '#/home'), quote=True)}">进入卡嘴子官网提交真实需求</a></header><section><h2>服务办理说明</h2><p>发布需求时请说明所在区域、服务类别、故障或任务现象和期望时间。维修项目应先检测、再提供明细报价，用户确认后施工；最终服务范围、到场时间和费用以真实订单为准。</p><p>水电安装维修、家电维修和管道疏通等现场项目，需要根据房屋、设备和故障实际情况判断。平台公开页用于帮助用户整理需求，不代替师傅现场检测，也不会预先承诺未经确认的价格、配件、工期或维修结果。</p><p>安装服务和个人任务同样需要写清地点、时间、物品规格、现场条件与验收要求。涉及高空、带电、燃气或其他安全风险时，应由具备相应条件的人员处理；用户不要在公开描述中填写门牌、电话、身份证等隐私信息。</p></section><section><h2>从需求到完工</h2><p>用户先通过正式入口提交需求，平台根据服务区域和类别连接合适的本地服务人员。双方确认沟通方式后，服务人员了解现场情况并给出方案；需要上门检测的项目，应把检测结果、报价明细、增项说明、用户确认和完工结果保留在真实订单或可核验记录中。</p><p>页面中的地区、服务类型和办理建议用于公开信息检索。真实响应速度、师傅是否接单、实际到场时间、材料选择及最终费用可能因供需和现场情况变化，均以双方确认及平台订单记录为准。</p></section><section><h2>公开服务页面</h2><ul>{links}</ul></section><section><h2>真实性说明</h2><p>公开页面已通过公网可访问、Canonical、结构化数据和可抓取正文检查。发布成功不等于搜索引擎已经抓取、收录或排名；相关结果仍以百度、Bing、Google等平台的真实证据为准。</p></section></main></body></html>'''
    return body.encode("utf-8")


def _sitemap_xml() -> bytes:
    snap = deployer.dashboard()
    config = snap.get("config") if isinstance(snap.get("config"), dict) else {}
    rows = sorted(
        [asset for asset in snap.get("assets", []) if str(asset.get("public_url") or "").startswith("https://")],
        key=lambda asset: str(asset.get("public_url") or ""),
    )
    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    hub_url = urllib.parse.urljoin(deployer._safe_public_base(config.get("site_base_url") or "https://kazuizhi.com/"), "seo/")
    entries = [f"  <url><loc>{html.escape(hub_url, quote=True)}</loc><lastmod>{now_iso()[:10]}</lastmod></url>"]
    entries.extend(
        f"  <url><loc>{html.escape(str(asset.get('public_url') or ''), quote=True)}</loc><lastmod>{str(asset.get('updated_at') or asset.get('published_at') or now_iso())[:10]}</lastmod></url>"
        for asset in rows
    )
    xml += "\n".join(entries)
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
    pending = [
        x for x in snap.get("assets", [])
        if x.get("stage") == "QC_PASSED" or bool(x.get("republish_pending"))
    ][: max(0, int(limit))]
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
            evidence = {
                "public_url": public_url,
                "connector": REMOTE_MODE,
                "deploy_receipt": receipt["receipt_id"],
                "remote_job_id": remote_receipt.get("job_id"),
                "http_verification": verification,
            }
            if asset.get("republish_pending"):
                seo_geo_growth.record_asset_republished(asset_id, evidence)
            else:
                deployer.record_asset_stage(asset_id, "PUBLISHED", evidence)
            published.append({"asset_id": asset_id, "public_url": public_url, "receipt": receipt["receipt_id"]})
        except (OSError, ValueError, RuntimeError) as error:
            failed.append({"asset_id": asset_id, "reason": str(error)})

    hub_result = {}
    try:
        hub_content = _seo_hub_html(base)
        hub_receipt = remote_agent.upload_bytes("seo/index.html", hub_content, job_id=_job_id("SEO-HUB", "SEO-HUB"))
        hub_url = urllib.parse.urljoin(base, "seo/")
        hub_public = _public_text(hub_url, timeout)
        hub_body = bytes(hub_public.get("body") or b"")
        hub_verified = bool(
            hub_public.get("status") == 200
            and b'<link rel="canonical"' in hub_body
            and b"application/ld+json" in hub_body
            and len(hub_body) >= 1500
        )
        hub_result = {
            "ok": hub_verified,
            "public_url": hub_url,
            "remote_job_id": hub_receipt.get("job_id"),
            "sha256": hub_receipt.get("sha256"),
            "status": hub_public.get("status"),
            "bytes": len(hub_body),
        }
    except (OSError, ValueError, RuntimeError) as error:
        hub_result = {"ok": False, "error": str(error)}

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
        "managed_seo_hub": hub_result,
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
