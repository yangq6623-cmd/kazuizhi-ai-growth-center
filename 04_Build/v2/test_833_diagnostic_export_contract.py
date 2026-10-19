"""Static safety gate for the #833 Windows read-only ledger exporter."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "04_Build" / "v2" / "Export-Kazuizhi833Diagnostics.ps1"


def main():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "growth_orchestrator.json" in text
    assert "seo_public_deploy_receipts.json" in text
    assert "geo_validation\\queue.json" in text
    assert "geo_validation\\receipts.json" in text
    assert "business\\remote_summary.json" in text
    assert "Get-FileHash" in text
    assert "Redact-Value" in text and "<redacted>" in text
    assert "business_readonly_key.bin" not in text.split("@\"")[0]
    forbidden = ("Invoke-WebRequest", "Invoke-RestMethod", "Start-Process", "Remove-Item", "Set-Content -LiteralPath $DataRoot")
    assert not any(value in text for value in forbidden), "exporter contains a mutation or network primitive"
    assert "production_mutations = 0" in text and "retries_triggered = 0" in text
    print("PASS: #833 exporter is local-read-only, redacted and hash-audited")


if __name__ == "__main__":
    main()
