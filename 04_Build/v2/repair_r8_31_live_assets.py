"""Rebuild the eight approved R8-31 pages in the durable live ledger.

This maintenance tool deliberately does not publish.  It creates a timestamped
backup, rewrites only the approved slugs with the current source generator, and
sets ``republish_pending`` so the normal audited remote deployer can publish and
verify them.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import seo_geo_growth as growth  # noqa: E402
from core.storage import data_root, now_iso  # noqa: E402


TARGET_SLUGS = {
    "12832e79ee6e2077",
    "47d230e4779eb965",
    "9c7e309e8d0ebd77",
    "077ab037e185be7b",
    "adadb41b67cec9e3",
    "16e00c783f72030a",
    "25393d85031d9460",
    "0e32f2e46acc9be0",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", action="store_true", help="record verified publication without rebuilding files")
    args = parser.parse_args()
    store = data_root() / growth.STORE
    state = growth._load()
    assets = {str(row.get("slug") or ""): row for row in state.get("assets", [])}
    missing = sorted(TARGET_SLUGS - set(assets))
    if missing:
        raise RuntimeError(f"Approved assets missing from ledger: {missing}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = data_root() / "r8_13" / "backups" / f"r8-31-live-repair-{stamp}"
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(store, backup / "seo_geo_growth.json")

    if args.finalize:
        finalized = []
        for slug in sorted(TARGET_SLUGS):
            asset = assets[slug]
            asset["public_template_version"] = growth.PUBLIC_TEMPLATE_VERSION
            asset["republish_pending"] = False
            asset["last_republished_at"] = now_iso()
            asset["updated_at"] = now_iso()
            finalized.append({"id": asset.get("id"), "slug": slug, "public_url": asset.get("public_url")})
        state.setdefault("audit", []).insert(0, {
            "at": now_iso(),
            "kind": "r8_31_live_template_repair_verified",
            "detail": {
                "slugs": sorted(TARGET_SLUGS),
                "template_version": growth.PUBLIC_TEMPLATE_VERSION,
                "backup": str(backup),
                "truth": "Remote deploy receipts and independent public HTTP checks completed before finalizing the ledger marker.",
            },
        })
        state["audit"] = state["audit"][:500]
        growth._save(state)
        print(json.dumps({"backup": str(backup), "finalized": finalized}, ensure_ascii=False))
        return

    facts = state.get("brand_facts") or growth.DEFAULT_BRAND_FACTS
    site = str(state.get("config", {}).get("site_base_url") or growth.DEFAULT_SITE).rstrip("/") + "/"
    repaired = []
    for slug in sorted(TARGET_SLUGS):
        asset = assets[slug]
        path = Path(str(asset.get("staging_path") or ""))
        if not path.is_file():
            raise RuntimeError(f"Missing staging file for {slug}: {path}")
        slug_backup = backup / "site_staging" / "seo" / slug
        slug_backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, slug_backup / "index.html")

        canonical = str(asset.get("canonical") or urljoin(site, f"seo/{slug}/"))
        related = [
            {"label": row.get("keyword") or row.get("service"), "url": urljoin(site, f"seo/{row.get('slug')}/")}
            for row in state.get("assets", [])
            if row.get("id") != asset.get("id") and row.get("slug")
            and (row.get("region") == asset.get("region") or row.get("service") == asset.get("service"))
        ]
        title, description, page = growth._render_page(asset, facts, canonical=canonical, related=related)
        path.write_text(page, encoding="utf-8")
        asset.update({
            "title": title,
            "description": description,
            "canonical": canonical,
            "generated_at": now_iso(),
            "updated_at": now_iso(),
            "public_template_version": growth.PUBLIC_TEMPLATE_VERSION,
            "republish_pending": True,
        })
        repaired.append({"id": asset.get("id"), "slug": slug, "public_url": asset.get("public_url") or canonical})

    state.setdefault("audit", []).insert(0, {
        "at": now_iso(),
        "kind": "r8_31_live_template_repair_staged",
        "detail": {
            "slugs": sorted(TARGET_SLUGS),
            "template_version": growth.PUBLIC_TEMPLATE_VERSION,
            "backup": str(backup),
            "truth": "Only approved pages were rebuilt; publication still requires the audited remote deployer receipt.",
        },
    })
    state["audit"] = state["audit"][:500]
    growth._save(state)
    print(json.dumps({"backup": str(backup), "repaired": repaired}, ensure_ascii=False))


if __name__ == "__main__":
    main()
