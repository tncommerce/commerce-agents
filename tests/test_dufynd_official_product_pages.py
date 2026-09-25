"""Guard curated manufacturer fallbacks against catalog and domain drift."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

CATALOG = Path("examples/retail/data/scentai_products.json")
PAGES = Path("examples/retail/storefront-web/lib/officialProductPages.ts")

# A manufacturer link is only a useful fallback if it points to that brand's site.
OFFICIAL_HOSTS = {
    "Louis Vuitton": "de.louisvuitton.com",
    "Essential Parfums": "www.essentialparfums.com",
    "Creed": "www.creedfragrance.de",
    "Dior": "www.dior.com",
    "Chanel": "www.chanel.com",
    "Prada": "www.prada-beauty.com",
    "Parfums de Marly": "parfums-de-marly.com",
    "Montblanc": "www.montblanc.com",
    "Valentino": "www.valentino-beauty.com",
    "Xerjoff": "www.xerjoff.com",
    "Giorgio Armani": "www.armanibeauty.de",
}

ENTRY = re.compile(
    r'"(?P<id>SC-[A-Z0-9-]+)":\s*\{\s*'
    r'merchant:\s*"(?P<merchant>[^"]+)",\s*'
    r'url:\s*"(?P<url>[^"]+)",\s*\}',
    re.MULTILINE,
)


def test_official_product_pages_match_catalog_and_manufacturer_domains() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    products = {product["product_id"]: product for product in catalog["products"]}
    source = PAGES.read_text(encoding="utf-8")
    entries = list(ENTRY.finditer(source))

    assert entries, "No curated official product pages found"
    assert source.count('url: "') == len(entries), "An entry escaped the fallback audit"
    assert len({match["id"] for match in entries}) == len(entries), "Duplicate product IDs"

    for match in entries:
        product_id = match["id"]
        assert product_id in products, f"Unknown product ID: {product_id}"

        product = products[product_id]
        host = urlparse(match["url"])
        assert host.scheme == "https" and not host.username and not host.password
        assert host.hostname == OFFICIAL_HOSTS[product["brand"]], product_id
        assert host.path not in ("", "/"), f"Expected product-specific URL: {product_id}"
