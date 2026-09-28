"""Keep DUFYND acquisition landing pages branded, premium and browser-covered."""

from pathlib import Path

ACQUISITION = Path("examples/retail/storefront-web/components/AcquisitionLanding.tsx")
VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_acquisition_landing_uses_dufynd_brand_and_live_catalog_context() -> None:
    source = ACQUISITION.read_text(encoding="utf-8")

    assert 'src="/icon.svg"' in source
    assert "LIVE_FRAGRANCES.length" in source
    assert 'href="/duft"' in source
    assert 'aria-label="So hilft DUFYND"' in source
    assert "Empfehlungen vor Provision." in source


def test_duftfinder_exercises_shared_acquisition_layout_in_visual_qa() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'name: "acquisition-duftfinder"' in source
    assert 'route: "/duftfinder"' in source
    assert "Persönliche Beratung starten" in source
