"""Keep internal/campaign utility routes out of search indexing."""

from pathlib import Path

SHOWCASE_LAYOUT = Path("examples/retail/storefront-web/app/showcase/layout.tsx")
START_PAGE = Path("examples/retail/storefront-web/app/start/page.tsx")
SEO_SCRIPT = Path("examples/retail/storefront-web/scripts/generate-launch-seo.mjs")


def test_internal_showcase_is_explicitly_noindex() -> None:
    source = SHOWCASE_LAYOUT.read_text(encoding="utf-8")

    assert "robots: {" in source
    assert "index: false" in source
    assert "follow: false" in source


def test_social_start_route_is_explicitly_noindex() -> None:
    source = START_PAGE.read_text(encoding="utf-8")

    assert 'canonical: "/start"' in source
    assert "robots: {" in source
    assert "index: false" in source
    assert "follow: false" in source


def test_utility_routes_are_not_generated_into_sitemap() -> None:
    source = SEO_SCRIPT.read_text(encoding="utf-8")

    routes_block = source.split("const routes = [", 1)[1].split("];", 1)[0]
    assert '"/start"' not in routes_block
    assert '"/showcase"' not in routes_block
