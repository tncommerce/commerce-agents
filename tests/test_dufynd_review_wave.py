"""Review waves are distinct products; SEO planning never means publication."""

import json
from pathlib import Path

DATA = Path("examples/retail/data")
WEB = Path("examples/retail/storefront-web")


def test_wave_does_not_duplicate_public_products_or_routes():
    pilots = json.loads((DATA / "dufynd_release_pilots.json").read_text())["pilots"]
    public = json.loads((WEB / "lib/generated/public-catalog.json").read_text())["products"]
    ids = [p["product_id"] for p in pilots]
    paths = [p["seo"]["public_path"] for p in pilots]
    assert len(ids) == len(set(ids)) >= 10
    assert len(paths) == len(set(paths))
    assert not set(ids) & {p["product_id"] for p in public}
    assert all(p["seo"]["public_path"] == f"/duft/{p['slug']}" for p in pilots)
    assert all(p["seo"]["description"] and p["seo"]["title"] for p in pilots)
    assert not any(p["owner_release_approved"] for p in pilots)


def test_lead_pilots_have_different_compositions_not_only_colors():
    pilots = json.loads((DATA / "dufynd_release_pilots.json").read_text())["pilots"]
    assert [p["motif"] for p in pilots[:3]] == ["blossom", "architecture", "embers"]
    art = (WEB / "components/ScentStudy.tsx").read_text()
    assert "<img" not in art and "https://" not in art
    assert "Duftillustration · kein Produktfoto" in art


def test_noindex_review_metadata_and_dynamic_navigation():
    page = (WEB / "app/review/duft/[slug]/page.tsx").read_text()
    assert "index:false,follow:false" in page
    assert "canonical:null" in page
    assert "generateMetadata" in page
    assert "fact.checked_at" in page
    assert "fact.identity.kind==='gtin'" in page
    assert "Keine erfundene Duftpyramide" in page
