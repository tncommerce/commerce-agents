"""Keep acquisition attribution covered on merchant clickout hrefs without executing them."""

from pathlib import Path

VISUAL_QA = Path("examples/retail/storefront-web/scripts/dufynd-visual-qa.mjs")


def test_merchant_clickout_attribution_is_browser_covered() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "merchant-clickout-attribution-link"' in source
    assert "rabanne-1-million?src=tiktok&cmp=qa_campaign&content=qa_content" in source
    assert 'a[href*="/api/clickout/"]' in source
    assert 'clickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'clickoutUrl.searchParams.get("cmp") !== "qa_campaign"' in source
    assert 'clickoutUrl.searchParams.get("content") !== "qa_content"' in source
    assert 'clickout.getAttribute("target")' in source


def test_acquisition_attribution_survives_internal_navigation() -> None:
    source = VISUAL_QA.read_text(encoding="utf-8")

    assert 'label: "acquisition-navigation-clickout-attribution"' in source
    assert "/start?src=tiktok&cmp=qa_navigation_campaign&content=qa_navigation_content" in source
    assert 'name: "Katalog entdecken"' in source
    assert 'a[href="/duft/rabanne-1-million"]' in source
    assert 'navClickoutUrl.searchParams.get("src") !== "tiktok"' in source
    assert 'navClickoutUrl.searchParams.get("cmp") !== "qa_navigation_campaign"' in source
    assert 'navClickoutUrl.searchParams.get("content") !== "qa_navigation_content"' in source
