"""R8-17 direct-file fallback for legacy IIS public SEO verification.

Windows Server 2012 R2 / IIS installations can serve a static .html file while
still refusing the directory-style URL /seo/<slug>/ because of Default Document
or handler configuration.  The normal R8-17 path remains the first choice.  If
that path was uploaded but fails truthful public verification, this module also
publishes /seo/<slug>.html with its canonical rewritten to that exact public
URL, verifies the direct file, and only then records PUBLISHED.

No IIS configuration is changed and no claim is advanced without real public
HTTP/content/canonical/Schema/robots evidence.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

from core.storage import now_iso
from integrations import remote_agent
from integrations import seo_public_deployer as deployer
from integrations import r8_17_remote_deployer_patch as remote_patch

_ORIGINAL_DEPLOY_PENDING = deployer.deploy_pending
_INSTALLED = False


def _rewrite_canonical(source: Path, old_canonical: str, new_canonical: str) -> bytes:
    text = source.read_text(encoding="utf-8")
    old = str(old_canonical or "").strip()
    new = str(new_canonical or "").strip()
    if not new.startswith("https://"):
        raise ValueError("flat fallback canonical must be HTTPS")
    if old:
        text = text.replace(old, new)
    # Generated R8 pages always contain the original canonical.  Refuse to emit
    # a fallback page if the replacement did not produce the exact new URL.
    if new not in text:
        raise ValueError("flat fallback canonical rewrite failed")
    return text.encode("utf-8")


def _asset_map() -> dict:
    snap = deployer.dashboard()
    return {
        str(row.get("id") or ""): row
        for row in snap.get("assets", [])
        if isinstance(row, dict) and row.get("id")
    }


def deploy_pending(limit: int = 10) -> dict:
    result = _ORIGINAL_DEPLOY_PENDING(limit=limit)
    if result.get("skipped") or not result.get("failed"):
        return result

    state = deployer.status()
    if state.get("mode") != remote_patch.REMOTE_MODE or not state.get("ready"):
        return result

    base = deployer._safe_public_base(state.get("public_base_url") or "https://kazuizhi.com/")
    timeout = int(deployer._load().get("verify_timeout_seconds") or 8)
    assets = _asset_map()
    published = list(result.get("published") or [])
    remaining_failed = []
    fallback_attempts = []

    for failure in list(result.get("failed") or []):
        asset_id = str(failure.get("asset_id") or "")
        if failure.get("reason") != "public_http_verification_failed":
            remaining_failed.append(failure)
            continue
        asset = assets.get(asset_id) or {}
        slug = str(asset.get("slug") or "").strip()
        source = Path(str(asset.get("staging_path") or ""))
        if not asset_id or not slug or "/" in slug or "\\" in slug or not source.is_file():
            remaining_failed.append(failure)
            continue

        flat_relative = f"seo/{slug}.html"
        flat_url = urllib.parse.urljoin(base, flat_relative)
        old_canonical = str(asset.get("canonical") or failure.get("public_url") or "")
        attempt = {
            "asset_id": asset_id,
            "primary_public_url": failure.get("public_url") or "",
            "fallback_public_url": flat_url,
            "at": now_iso(),
        }
        try:
            payload = _rewrite_canonical(source, old_canonical, flat_url)
            remote_receipt = remote_agent.upload_bytes(
                flat_relative,
                payload,
                job_id=remote_patch._job_id(asset_id, "SEOFLAT"),
            )
            verification = deployer._verify_public_url(
                flat_url,
                str(asset.get("title") or ""),
                flat_url,
                timeout,
            )
            receipt = {
                "receipt_id": f"REMOTE-FLAT-{asset_id}-{now_iso().replace(':','').replace('-','')}",
                "asset_id": asset_id,
                "connector": remote_patch.REMOTE_MODE,
                "strategy": "direct_html_file",
                "remote_job_id": remote_receipt.get("job_id"),
                "remote_sha256": remote_receipt.get("sha256"),
                "destination": flat_relative,
                "public_url": flat_url,
                "verification": verification,
                "created_at": now_iso(),
            }
            deployer._append_receipt(receipt)
            attempt["verification"] = verification
            if not verification.get("ok"):
                failure = dict(failure)
                failure["flat_fallback"] = attempt
                remaining_failed.append(failure)
                fallback_attempts.append(attempt)
                continue

            deployer.record_asset_stage(asset_id, "PUBLISHED", {
                "public_url": flat_url,
                "connector": remote_patch.REMOTE_MODE,
                "deploy_receipt": receipt["receipt_id"],
                "remote_job_id": remote_receipt.get("job_id"),
                "http_verification": verification,
                "public_url_strategy": "direct_html_file",
            })
            published.append({
                "asset_id": asset_id,
                "public_url": flat_url,
                "receipt": receipt["receipt_id"],
                "strategy": "direct_html_file",
            })
            attempt["ok"] = True
            fallback_attempts.append(attempt)
        except (OSError, ValueError, RuntimeError) as error:
            attempt["ok"] = False
            attempt["error"] = str(error)
            failure = dict(failure)
            failure["flat_fallback"] = attempt
            remaining_failed.append(failure)
            fallback_attempts.append(attempt)

    result = dict(result)
    result["published"] = published
    result["failed"] = remaining_failed
    result["flat_fallback_attempts"] = fallback_attempts
    result["truth"] = (
        "Directory URL remains preferred. If legacy IIS rejects /seo/<slug>/, "
        "R8-17 may use verified /seo/<slug>.html. PUBLISHED is still recorded "
        "only after real HTTP/content/canonical/Schema/robots verification."
    )
    data = deployer._load()
    data["last_result"] = result
    data["last_run_at"] = now_iso()
    deployer._save(data)
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    deployer.deploy_pending = deploy_pending
    _INSTALLED = True


install()
