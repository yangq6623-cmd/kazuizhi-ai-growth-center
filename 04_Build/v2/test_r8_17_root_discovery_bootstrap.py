"""Release gate for the server-local root robots/sitemap repair helper."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from core import r8_17_root_discovery_bootstrap as bootstrap


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="kz-r817-root-") as temp:
        root = Path(temp)
        hits = {}

        def missing_then_live(url):
            hits[url] = hits.get(url, 0) + 1
            status = 404 if hits[url] == 1 else 200
            return {"ok": status == 200, "status": status, "url": url}

        report = bootstrap.execute(root, "https://kazuizhi.example/", fetch_status=missing_then_live)
        require(report["verified"], "created root files were not publicly verified")
        require(report["exit_code"] == 0, "verified creation has a failing exit code")
        require((root / "robots.txt").is_file() and (root / "sitemap.xml").is_file(), "root files were not created")
        require(b"Sitemap: https://kazuizhi.example/seo/sitemap.xml" in (root / "robots.txt").read_bytes(), "robots misses managed sitemap")

    with tempfile.TemporaryDirectory(prefix="kz-r817-preserve-") as temp:
        root = Path(temp)
        existing = root / "robots.txt"
        existing.write_text("site-owned", encoding="utf-8")
        report = bootstrap.execute(root, "https://kazuizhi.example/", fetch_status=lambda url: {"ok": False, "status": 404, "url": url})
        require(existing.read_text(encoding="utf-8") == "site-owned", "existing site-owned robots file was overwritten")
        require(report["files"]["robots.txt"]["preserved"], "existing robots file was not marked preserved")
        require(report["files"]["robots.txt"]["reason"] == "local_file_exists_public_404_preserved", "preservation reason is inaccurate")

    print("R8-17 server-local root discovery bootstrap gate: PASS")


if __name__ == "__main__":
    main()
