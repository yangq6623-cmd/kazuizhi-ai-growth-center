from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from backend.r8_13_seo_geo_patch import _normalized_asset_signals  # noqa: E402
from core.seo_geo_growth import source_tracking_id  # noqa: E402
from integrations.seo_public_deployer import publication_scope_allowed  # noqa: E402


def main():
    first = {"id": "SEO-A9F101F09594", "region": "涟水县", "service": "水电维修"}
    second = {"id": "SEO-EFD627922BFA", "region": "涟水县", "service": "家电维修"}
    first_source = source_tracking_id(first)
    second_source = source_tracking_id(second)
    normalized, aliases, unmatched, anomalies = _normalized_asset_signals(
        {
            "by_source": {
                first_source: {"landing": 3, "open_click": 3},
                second_source: {"landing": 0, "open_click": 1},
                "KZSEO-FC32097EBE81": {"landing": 1, "open_click": 0},
                "unattributed": {"landing": 0, "open_click": 1},
            },
            "by_asset": {
                "SEO-123456789ABC": {"landing": 3, "open_click": 3},
                "SEO-F89F1879EDEF": {"landing": 1, "open_click": 0},
                "unattributed": {"landing": 0, "open_click": 2},
            },
        },
        [first, second],
    )
    assert aliases[first_source] == first["id"]
    assert aliases[second_source] == second["id"]
    assert normalized[first["id"]] == {"landing": 3, "open_click": 3}
    assert normalized[second["id"]] == {"landing": 0, "open_click": 1}
    assert normalized["未归因"] == {"landing": 1, "open_click": 1}
    assert sum(row["landing"] for row in normalized.values()) == 4
    assert sum(row["open_click"] for row in normalized.values()) == 5
    assert set(unmatched) == {"KZSEO-FC32097EBE81", "unattributed"}
    assert set(anomalies) == {"SEO-123456789ABC", "SEO-F89F1879EDEF", "unattributed"}

    assert publication_scope_allowed({"hero_image_url": "https://kazuizhi.com/seo/assets/hero.webp"})
    assert not publication_scope_allowed({"hero_image_url": "https://other.example/hero.webp"})
    assert not publication_scope_allowed({"hero_image_url": "https://kazuizhi.com/seo/assets/kazuizhi-mini-program-code.jpg"})
    assert publication_scope_allowed({"republish_pending": True})
    assert publication_scope_allowed({"publish_approved": True})
    assert not publication_scope_allowed({
        "id": "SEO-50AAE9309BF1",
        "phase3_targeted": True,
        "phase3_source": "GEO Growth OS · C-level Signal · service_coverage_missing",
    })
    print("R8-33 P0 growth regression verification passed")


if __name__ == "__main__":
    main()
