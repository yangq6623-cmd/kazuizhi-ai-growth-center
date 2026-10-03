from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def text(path):
    return path.read_text(encoding="utf-8")


def test_late_runtime_patch_chain_is_loaded_by_packaged_entrypoint_path():
    source = text(SRC / "promotion" / "chatgpt_mission_patch.py")
    required = [
        "r8_22_autonomy_convergence_patch",
        "r8_23_growth_os_patch",
        "r8_23_2_runtime_truth_patch",
        "r8_23_2_runtime_safety_patch",
        "r8_23_3_candidate_patch",
        "r8_23_4_runtime_route_recovery_patch",
        "r8_23_5_full_recovery_patch",
    ]
    for name in required:
        assert name in source, name


def test_browser_bundle_keeps_all_post_r8_19_layers():
    source = text(SRC / "backend" / "r8_23_5_full_recovery_patch.py")
    required = [
        "r8_13_seo_geo_bridge.js",
        "operational-search.js",
        "geo-autonomy.js",
        "geo-phase3.js",
        "seo-geo-growth-intelligence.js",
        "seo-geo-connector-matrix.js",
        "r8_22_autonomy.js",
        "r8_23_growth_os.js",
        "r8_23_2_pilot.js",
        "r8_23_3_candidate.js",
        "r8_23_4_recovery.js",
        "r8_23_5_full_recovery.js",
    ]
    for name in required:
        assert name in source, name
        assert (SRC / "web" / name).exists(), name


def test_existing_seo_geo_buttons_are_bound_not_only_newly_created_buttons():
    source = text(SRC / "web" / "r8_23_5_full_recovery.js")
    assert 'button.nav[data-page="r813-seo-geo"]' in source
    assert '.r810-primary-nav [data-target="r813-seo-geo"]' in source
    assert "KZR813SeoGeoBridge" in source
    assert "addEventListener('click', openSeoGeo" in source


def test_recovery_identity_no_longer_reports_legacy_20_of_20_baseline():
    source = text(SRC / "web" / "r8_23_5_full_recovery.js")
    assert "R8-23.5 Full Regression Recovery" in source
    assert "功能恢复 20 / 20" not in source
