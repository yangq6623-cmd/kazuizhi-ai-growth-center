"""Focused contract checks for the R8-18 version/evidence foundation."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / "05_V2.0.0_Source"
    old_local = os.environ.get("LOCALAPPDATA")
    sys.path.insert(0, str(source))
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        import core.growth_evidence as ledger
        from core.version import get_version, release_manifest

        manifest = release_manifest()
        assert manifest["baseline"]["github_run"] == "#76"
        assert manifest["candidate"]["package_status"] == "not_packaged"
        assert get_version()["release_manifest"]["baseline"]["commit"] == "6e8270e"

        original = ledger.STORE
        try:
            ledger.STORE = "r8_18_test/growth_evidence.json"
            # A blank ledger must be read-only and must not invent external results.
            snapshot = ledger.status()
            assert snapshot["summary"]["total"] == 0
            assert snapshot["summary"]["external"] == 0

        # Dedupe is essential: re-importing the same receipt cannot inflate KPIs.
            data = ledger._load()
            assert ledger._append(data, kind="search_submission_receipt", source="test", reference="receipt-1", observed_at="2026-09-28T00:00:00+08:00", payload={"receipt": "receipt-1"}, external=True)
            assert not ledger._append(data, kind="search_submission_receipt", source="test", reference="receipt-1", observed_at="2026-09-28T00:00:00+08:00", payload={"receipt": "receipt-1"}, external=True)
            ledger._save(data)
            snapshot = ledger.status()
            assert snapshot["summary"]["total"] == 1
            assert snapshot["summary"]["external"] == 1
            assert snapshot["summary"]["by_kind"]["search_submission_receipt"] == 1
        finally:
            ledger.STORE = original
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            sys.path.remove(str(source))

    print("R8-18 evidence ledger checks passed")

    ui = (source / "web" / "integrations.js").read_text(encoding="utf-8")
    assert "/api/r8-18/release-manifest" in ui
    assert "/api/r8-18/evidence-ledger/refresh" in ui
    assert "refreshEvidenceLedger" in ui
    print("R8-18 evidence ledger UI contract checks passed")


if __name__ == "__main__":
    main()
