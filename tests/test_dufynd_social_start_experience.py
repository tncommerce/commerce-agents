"""Keep the DUFYND social entry page immersive, branded and conversion-oriented."""

from pathlib import Path

START_PAGE = Path("examples/retail/storefront-web/app/start/page.tsx")
VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_social_start_exposes_the_four_primary_entry_paths() -> None:
    source = START_PAGE.read_text(encoding="utf-8")

    assert "Finde deinen schnellsten Weg zum passenden Duft." in source
    assert 'src="/icon.svg"' in source
    assert 'href: "/duftfinder"' in source
    assert 'href: "/duft"' in source
    assert 'href: "/parfum-alternativen"' in source
    assert 'href: "/parfum-geschenkberater"' in source
    assert "LIVE_FRAGRANCES.length" in source


def test_social_start_is_covered_by_responsive_visual_qa() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'name: "social-start"' in source
    assert 'route: "/start"' in source
    assert "requiredEntryPaths" in source
