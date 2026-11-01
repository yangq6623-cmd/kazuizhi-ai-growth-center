"""Static safety contract; PowerShell execution still requires Windows testing."""
from pathlib import Path


source = (Path(__file__).with_name("Export-Kazuizhi891ReadOnly.ps1")
          .read_text(encoding="utf-8"))
assert "-Method Get" in source
assert "-Method Post" not in source and "-Method Put" not in source
assert "http://127.0.0.1:8876" in source
assert "if ($BaseUrl.TrimEnd('/') -ne 'http://127.0.0.1:8876')" in source
assert "New-Item -ItemType Directory -Path $OutputDirectory" in source
assert "Set-Content -LiteralPath $target" in source
assert "-LiteralPath $DataRoot" not in source.split("Set-Content")[-1]
for forbidden in ("shared_secret", "raw_answer", "Get-Credential", "Invoke-RestMethod", "Start-Process"):
    assert forbidden not in source, forbidden
for required in ("async_control_bus_state.json", "geo_validation\\queue.json", "seo_geo_growth.json", "content_center.json", "r8_17\\remote_agent.json"):
    assert required in source, required
print("PASS: #891 diagnostic export is local GET plus redacted ledger projection only")
