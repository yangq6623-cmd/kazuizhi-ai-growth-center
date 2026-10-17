"""Add a stable, non-personal source ID to generated SEO staging pages.

The ID is metadata only. It carries no user identity and lets website/mini-program
analytics later join real visit/consultation/task/order events to the originating
SEO asset without changing canonical URLs.
"""
from __future__ import annotations

import hashlib

from core import seo_geo_growth

_INSTALLED = False
_ORIGINAL_RENDER = seo_geo_growth._render_page


def source_tracking_id(asset):
    key = str((asset or {}).get("id") or (asset or {}).get("opportunity_id") or (asset or {}).get("keyword") or "unknown")
    return "KZSRC-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:14].upper()


def _render(asset, facts):
    title, description, html = _ORIGINAL_RENDER(asset, facts)
    source_id = source_tracking_id(asset)
    marker = f'<meta name="kazuizhi-source-id" content="{source_id}">'
    if marker not in html and "<head>" in html:
        html = html.replace("<head>", "<head>" + marker, 1)
    return title, description, html


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    seo_geo_growth._render_page = _render
    _INSTALLED = True


install()
