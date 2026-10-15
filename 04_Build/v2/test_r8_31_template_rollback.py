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
    assert 'data-kz-role="hero"' in page
    assert 'data-kz-role="mini-program-code"' in page
    inspected = deployer._inspect_public_html(page, title, "https://kazuizhi.com/seo/test/")
    assert inspected["template_version"] == growth.PUBLIC_TEMPLATE_VERSION
    assert inspected["mini_program_entry_present"] is True
    assert inspected["mini_program_image_present"] is True
    print("R8-31 template rollback guard verification passed")


if __name__ == "__main__":
    main()
