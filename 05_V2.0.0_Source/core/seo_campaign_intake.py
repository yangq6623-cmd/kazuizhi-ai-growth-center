"""Owner-approved campaign intake for the truthful SEO publication pipeline.

This module fills the gap between an approved copy/image package and the
existing R8 SEO stages.  An import creates a GENERATED asset only.  QC,
PUBLISHED and SUBMITTED remain controlled by their existing evidence gates.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import html
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath

from core import seo_geo_growth as growth
from core.storage import data_root, now_iso

MAX_COPY_CHARS = 20_000
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}


def _clean_text(value, *, limit, required=False, label="字段"):
    text = str(value or "").replace("\x00", "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}不能超过 {limit} 个字符")
    return text


def _safe_filename(value, mime_type):
    suffixes = ALLOWED_IMAGE_TYPES[mime_type]
    raw = Path(str(value or "campaign-image")[:160]).name
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(raw).stem).strip("-") or "campaign-image"
    suffix = Path(raw).suffix.lower()
    if suffix not in suffixes:
        suffix = suffixes[0]
    return f"{stem[:72]}{suffix}"


def _decode_image(payload):
    encoded = str(payload.get("image_base64") or "").strip()
    mime_type = str(payload.get("image_mime") or "").strip().lower()
    if not encoded:
        return None
    if encoded.startswith("data:"):
        header, _, encoded = encoded.partition(",")
        if ";base64" not in header:
            raise ValueError("图片必须使用 base64 编码")
        mime_type = header[5:].split(";", 1)[0].lower()
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("图片仅支持 JPG、PNG 或 WebP")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("图片 base64 数据无效") from error
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("图片不能为空且不能超过 5MB")
    valid = (
        (mime_type == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
        or (mime_type == "image/jpeg" and raw.startswith(b"\xff\xd8\xff"))
        or (mime_type == "image/webp" and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP")
    )
    if not valid:
        raise ValueError("图片内容与文件类型不一致")
    return {
        "bytes": raw,
        "mime_type": mime_type,
        "filename": _safe_filename(payload.get("image_name"), mime_type),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _copy_to_html(text):
    """Render a deliberately small, escaped Markdown subset."""
    blocks = []
    list_items = []

    def flush_list():
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            flush_list()
            continue
        if line.startswith(("- ", "* ")):
            list_items.append(line[2:].strip())
            continue
        flush_list()
        if line.startswith("### "):
            blocks.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            blocks.append(f"<h2>{html.escape(line[2:].strip())}</h2>")
        else:
            blocks.append(f"<p>{html.escape(line)}</p>")
    flush_list()
    return "".join(blocks)


def _validate_attachment(relative_path):
    pure = PurePosixPath(str(relative_path or ""))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError("素材相对路径无效")
    return pure.as_posix()


def _stage_campaign_asset(data, asset, image):
    site = str(data["config"].get("site_base_url") or growth.DEFAULT_SITE).rstrip("/") + "/"
    staging = data_root() / "r8_13" / "site_staging"
    folder = staging / "seo" / asset["slug"]
    folder.mkdir(parents=True, exist_ok=True)
    canonical = growth.urljoin(site, f"seo/{asset['slug']}/")
    related = [
        {"label": row.get("keyword") or row.get("service"), "url": growth.urljoin(site, f"seo/{row.get('slug')}/")}
        for row in data.get("assets", [])
        if row.get("id") != asset.get("id") and row.get("slug")
        and (row.get("region") == asset.get("region") or row.get("service") == asset.get("service"))
    ]
    title, description, page = growth._render_page(asset, data.get("brand_facts") or growth.DEFAULT_BRAND_FACTS, canonical=canonical, related=related)
    content = _copy_to_html(asset.get("campaign_body"))
    media_html = ""
    attachments = []
    if image:
        media_dir = folder / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        image_path = media_dir / image["filename"]
        image_path.write_bytes(image["bytes"])
        relative_path = _validate_attachment(f"media/{image['filename']}")
        attachments.append({
            "kind": "campaign_image",
            "path": str(image_path),
            "relative_path": relative_path,
            "mime_type": image["mime_type"],
            "sha256": image["sha256"],
        })
        media_html = (
            '<figure data-kz-role="campaign-image" style="margin:20px 0">'
            f'<img src="./{html.escape(relative_path, quote=True)}" alt="{html.escape(asset.get("campaign_title") or asset.get("keyword") or "卡嘴子本地服务", quote=True)}" '
            'style="width:100%;height:auto;border-radius:16px" loading="lazy">'
            '<figcaption class="proof">卡嘴子自有或已获授权的本轮推广素材</figcaption></figure>'
        )
    campaign_section = (
        '<section data-kz-role="campaign-content">'
        f'<h2>{html.escape(asset.get("campaign_title") or asset.get("keyword") or "服务说明")}</h2>'
        f'<p class="fit">{html.escape(asset.get("campaign_summary") or description)}</p>'
        f'{media_html}{content}</section>'
    )
    marker = "<section><h2>相关页面</h2>"
    page = page.replace(marker, campaign_section + marker, 1) if marker in page else page.replace("</article>", campaign_section + "</article>", 1)
    path = folder / "index.html"
    path.write_text(page, encoding="utf-8")
    asset.update({
        "stage": "GENERATED",
        "title": title,
        "description": description,
        "canonical": canonical,
        "staging_path": str(path),
        "staging_attachments": attachments,
        "generated_at": now_iso(),
        "updated_at": now_iso(),
        "public_template_version": growth.PUBLIC_TEMPLATE_VERSION,
    })
    growth._write_staging_infrastructure(data, staging, site)
    return asset


def import_campaign(payload):
    payload = dict(payload or {})
    if not payload.get("rights_confirmed"):
        raise ValueError("必须确认文案和图片为自有或已取得发布授权")
    region = _clean_text(payload.get("region") or growth.DEFAULT_REGION, limit=40, required=True, label="地区")
    service = _clean_text(payload.get("service"), limit=60, required=True, label="服务类型")
    keyword = _clean_text(payload.get("keyword"), limit=100, required=True, label="关键词")
    title = _clean_text(payload.get("title") or keyword, limit=120, required=True, label="标题")
    summary = _clean_text(payload.get("summary"), limit=300, required=True, label="摘要")
    body = _clean_text(payload.get("content"), limit=MAX_COPY_CHARS, required=True, label="正文")
    image = _decode_image(payload)
    content_sha = hashlib.sha256((title + "\n" + summary + "\n" + body + "\n" + (image or {}).get("sha256", "")).encode("utf-8")).hexdigest()
    requested_id = _clean_text(payload.get("campaign_id"), limit=80)
    campaign_id = requested_id or growth._stable_id("CAMPAIGN", region, service, keyword, content_sha[:16])
    data = growth._load()
    existing = next((row for row in data.get("assets", []) if row.get("campaign_id") == campaign_id and row.get("campaign_content_sha256") == content_sha), None)
    if existing:
        return {"created": False, "idempotent": True, "campaign_id": campaign_id, "asset": deepcopy(existing)}
    if any(row.get("campaign_id") == campaign_id for row in data.get("assets", [])):
        campaign_id = f"{campaign_id[:60]}-{content_sha[:10].upper()}"
    opportunity_id = growth._stable_id("KW", region, service, keyword, campaign_id)
    asset_id = growth._stable_id("SEO", region, service, keyword, campaign_id)
    slug = growth._slug(f"{region}-{service}-{keyword}-{campaign_id}")
    opportunity = {
        "id": opportunity_id,
        "region": region,
        "service": service,
        "keyword": keyword,
        "intent": _clean_text(payload.get("intent") or "交易", limit=30),
        "priority": _clean_text(payload.get("priority") or "S", limit=1).upper(),
        "status": "PLANNED",
        "source": "owner_campaign_import",
        "campaign_id": campaign_id,
        "discovered_at": now_iso(),
        "asset_id": asset_id,
    }
    asset = {
        "id": asset_id,
        "opportunity_id": opportunity_id,
        "campaign_id": campaign_id,
        "campaign_content_sha256": content_sha,
        "campaign_title": title,
        "campaign_summary": summary,
        "campaign_body": body,
        "campaign_rights": "owner_confirmed",
        "publish_approved": True,
        "region": region,
        "service": service,
        "keyword": keyword,
        "intent": opportunity["intent"],
        "priority": opportunity["priority"] if opportunity["priority"] in {"S", "A", "B", "C"} else "S",
        "page_type": "推广内容页",
        "slug": slug,
        "stage": "PLANNED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "public_url": "",
        "canonical": "",
        "submission_receipts": [],
        "crawl_evidence": [],
        "index_evidence": [],
        "rankings": [],
        "geo_mentions": [],
        "conversions": [],
    }
    data.setdefault("opportunities", []).append(opportunity)
    data.setdefault("assets", []).append(asset)
    _stage_campaign_asset(data, asset, image)
    opportunity["status"] = "GENERATED"
    data.setdefault("campaign_imports", []).insert(0, {
        "campaign_id": campaign_id,
        "asset_id": asset_id,
        "content_sha256": content_sha,
        "has_image": bool(image),
        "created_at": now_iso(),
    })
    data["campaign_imports"] = data["campaign_imports"][:200]
    growth._audit_event(data, "owner_campaign_imported", {
        "campaign_id": campaign_id,
        "asset_id": asset_id,
        "has_image": bool(image),
        "truth": "导入仅计为 GENERATED；发布与搜索提交仍需真实回执。",
    })
    growth._save(data)
    return {"created": True, "idempotent": False, "campaign_id": campaign_id, "asset": deepcopy(asset)}
