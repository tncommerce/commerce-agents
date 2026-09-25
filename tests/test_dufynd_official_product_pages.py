"""Guard curated manufacturer fallbacks against catalog and domain drift."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

CATALOG = Path("examples/retail/data/scentai_products.json")
PAGES = Path("examples/retail/storefront-web/lib/officialProductPages.ts")

# A fallback is only useful if it points to the manufacturer or official brand operator.
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
    "Afnan Perfumes": "de.afnan.com",
    "Sospiro": "sospirointernational.com",
    "Al Haramain": "shop.alharamainperfumes.com",
    "Clive Christian": "eu.clivechristian.com",
    "Maison Asrar": "maisonasrar.com",
    "Al Wataniah": "www.alwataniah.com",
    "Armaf": "armaf.com",
    "Arabiyat Prestige": "arabiyatprestige.com",
    "Rayhaan": "rayhaanperfumes.com",
    "Bvlgari": "www.bulgari.com",
    "French Avenue": "frenchavenue.com",
    "Orientica": "www.orienticaperfumes.com",
    "Al Ambra": "alambraperfumes.com",
    "Bujairami": "bujairami.com.au",
    "Nusuk": "www.riiffsperfumes.com",
}

ENTRY = re.compile(
    r'"(?P<id>SC-[A-Z0-9-]+)":\s*\{\s*'
    r'merchant:\s*"(?P<merchant>[^"]+)",\s*'
    r'url:\s*"(?P<url>[^"]+)",\s*\}',
    re.MULTILINE,
)

INTENTIONALLY_UNRESOLVED: set[str] = set()


def test_official_product_pages_match_catalog_and_manufacturer_domains() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    products = {product["product_id"]: product for product in catalog["products"]}
    source = PAGES.read_text(encoding="utf-8")
    entries = list(ENTRY.finditer(source))

    assert entries, "No curated official product pages found"
    assert source.count('url: "') == len(entries), "An entry escaped the fallback audit"
    covered_ids = {match["id"] for match in entries}
    assert len(covered_ids) == len(entries), "Duplicate product IDs"
    assert set(products) - covered_ids == INTENTIONALLY_UNRESOLVED
    assert len(covered_ids) == 32

    for match in entries:
        product_id = match["id"]
        assert product_id in products, f"Unknown product ID: {product_id}"

        product = products[product_id]
        host = urlparse(match["url"])
        assert host.scheme == "https" and not host.username and not host.password
        assert host.hostname == OFFICIAL_HOSTS[product["brand"]], product_id
        assert host.path not in ("", "/"), f"Non-product URL: {product_id}"
