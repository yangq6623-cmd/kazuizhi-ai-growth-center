from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import seo_geo_growth as growth  # noqa: E402
from integrations import seo_public_deployer as deployer  # noqa: E402


def main():
    asset = {
        "id": "SEO-TEST",
        "slug": "test",
        "region": "涟水县",
        "service": "水电安装维修",
        "keyword": "涟水水电维修",
        "hero_image_url": "https://kazuizhi.com/seo/assets/test-professional.webp",
    }
    facts = dict(growth.DEFAULT_BRAND_FACTS)
    facts["official_site"] = "https://kazuizhi.com/"
    title, _, page = growth._render_page(
        asset,
        facts,
        canonical="https://kazuizhi.com/seo/test/",
    )
    assert growth.PUBLIC_TEMPLATE_VERSION == "R8-31-mini-program-primary-v5"
    assert growth._template_revision("R8-31-mini-program-primary-v5") == 31
    assert growth._template_revision("R8-32-next") > growth._template_revision(growth.PUBLIC_TEMPLATE_VERSION)
    assert 'href="https://kazuizhi.com/open/?kz_source=KZSEO-' in page
    assert 'data-kz-entry="mini-program"' in page
    assert 'data-kz-role="professional-hero"' in page
    assert 'data-kz-role="professional-hero-image"' in page
    assert 'https://kazuizhi.com/seo/assets/test-professional.webp' in page
    assert '<meta property="og:image"' in page
    assert 'primaryImageOfPage' in page
    assert 'data-kz-role="mini-program-entry"' in page
    assert 'data-kz-role="mini-program-code"' in page
    inspected = deployer._inspect_public_html(page, title, "https://kazuizhi.com/seo/test/")
    assert inspected["template_version"] == growth.PUBLIC_TEMPLATE_VERSION
    assert inspected["mini_program_entry_present"] is True
    assert inspected["mini_program_image_present"] is True
    assert inspected["professional_hero_image_present"] is True
    assert inspected["professional_hero_image_urls"] == [asset["hero_image_url"]]
    assert asset["hero_image_url"] in inspected["professional_hero_image_urls"]
    contract = deployer._apply_professional_hero_contract(asset, {"ok": True, **inspected})
    assert contract["professional_hero_contract_ok"] is True
    assert contract["ok"] is True

    unsafe = dict(asset)
    unsafe["hero_image_url"] = "https://other.example/seo/assets/not-owned.webp"
    _, _, unsafe_page = growth._render_page(unsafe, facts, canonical="https://kazuizhi.com/seo/test/")
    assert 'data-kz-role="professional-hero-image"' not in unsafe_page
    qr_as_hero = dict(asset)
    qr_as_hero["hero_image_url"] = "https://kazuizhi.com/seo/assets/kazuizhi-mini-program-code.jpg"
    _, _, qr_page = growth._render_page(qr_as_hero, facts, canonical="https://kazuizhi.com/seo/test/")
    qr_inspected = deployer._inspect_public_html(qr_page, title, "https://kazuizhi.com/seo/test/")
    assert qr_inspected["mini_program_image_present"] is True
    assert qr_inspected["professional_hero_image_present"] is False
    failed_contract = deployer._apply_professional_hero_contract(
        asset, {"ok": True, **qr_inspected},
    )
    assert failed_contract["professional_hero_contract_ok"] is False
    assert failed_contract["ok"] is False
    print("R8-31 template rollback guard verification passed")


if __name__ == "__main__":
    main()
