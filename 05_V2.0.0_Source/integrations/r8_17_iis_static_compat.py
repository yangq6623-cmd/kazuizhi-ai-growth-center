"""R8-17 IIS static-page compatibility shim.

The production host is Windows Server 2012 R2 / IIS. Some IIS sites do not
include index.html in the effective Default Document list even though they can
serve static HTML files directly. R8-17 therefore mirrors every managed SEO
index.html to default.htm as a harmless static compatibility copy.

The canonical/public URL stays /seo/<slug>/ and truth gating is unchanged: the
page is still PUBLISHED only after the existing public HTTP/content/canonical/
Schema/robots verification passes.
"""
from __future__ import annotations

from pathlib import Path

from . import remote_agent

_ORIGINAL_UPLOAD_FILE = remote_agent.upload_file
_INSTALLED = False


def _mirror_path(relative_path: str) -> str:
    relative = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
    lower = relative.lower()
    if not lower.startswith("seo/") or not lower.endswith("/index.html"):
        return ""
    return relative[: -len("index.html")] + "default.htm"


def upload_file(relative_path: str, source: str | Path, *, job_id: str = "") -> dict:
    """Upload the canonical index file and an IIS Default.htm compatibility copy."""
    primary = _ORIGINAL_UPLOAD_FILE(relative_path, source, job_id=job_id)
    mirror = _mirror_path(relative_path)
    if not mirror:
        return primary

    mirror_job = (str(job_id or "R817-SEO") + "-DEFAULT")[:96]
    mirror_receipt = _ORIGINAL_UPLOAD_FILE(mirror, source, job_id=mirror_job)
    result = dict(primary or {})
    result["iis_default_document_mirror"] = {
        "relative_path": mirror,
        "job_id": mirror_receipt.get("job_id"),
        "sha256": mirror_receipt.get("sha256"),
        "ok": bool(mirror_receipt.get("ok", True)),
    }
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    remote_agent.upload_file = upload_file
    _INSTALLED = True


install()
