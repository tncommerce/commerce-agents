"""Shared, offline DUFYND merchant and exact-variant release gates.

No network access, no link generation, no product or image publication.
Only previously approved canonical affiliate URLs may be reused.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from scripts.validate_dufynd_catalog_expansion_wave import valid_gtin


def merchant_key(value: object) -> str:
    key = str(value or "").strip().casefold()
    return key[:-3] if key.endswith("-de") else key


def approved_affiliate_route(offer: dict, partners: dict) -> bool:
    """An old row in merchant_offers.json does not itself grant merchant approval."""
    merchant = merchant_key(offer.get("merchant_id"))
    matches = [
        row
        for row in partners.get("partners", [])
        if merchant_key(row.get("merchant_id")) == merchant
    ]
    if len(matches) != 1:
        return False
    partner = matches[0]
    status = partner.get("status")
    if status not in {"active", "active_product_deeplink_only"}:
        return False
    if status == "active_product_deeplink_only":
        if partner.get("live_routing_allowed") is not True:
            return False
        if offer.get("product_id") not in partner.get("verified_product_scope", []):
            return False

    link = offer.get("affiliate_url")
    if not isinstance(link, str):
        return False
    try:
        url = urlsplit(link)
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or url.fragment
            or url.port is not None
        ):
            return False
        host = (url.hostname or "").casefold().rstrip(".")
        params = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
        destination = str(offer.get("product_url") or "")
        if offer.get("network") == "CJ Affiliate":
            return (
                merchant == "notino"
                and host in {"jdoqocy.com", "www.jdoqocy.com"}
                and re.fullmatch(r"/click-[0-9]+-[0-9]+", url.path) is not None
                and params.get("url") == [destination]
            )
        if offer.get("network") == "Awin":
            expected_advertiser = {
                "perfumetrader": "11672",
                "top-parfuemerie": "31081",
            }.get(merchant)
            return (
                expected_advertiser is not None
                and host in {"awin1.com", "www.awin1.com"}
                and url.path == "/cread.php"
                and params.get("awinmid") == [expected_advertiser]
                and params.get("awinaffid") == ["3099222"]
                and params.get("ued") == [destination]
            )
    except ValueError:
        return False
    return False


def verify_exact_variant(
    offer: dict,
    observation: dict,
    catalog: dict,
    mappings: dict,
) -> None:
    """Bind a new source observation to approved merchant SKU, GTIN and strength."""
    products = [
        row
        for row in catalog.get("products", [])
        if row.get("product_id") == offer.get("product_id")
    ]
    if len(products) != 1:
        raise ValueError("canonical_catalog_product_missing_or_ambiguous")
    product = products[0]
    attrs = product.get("attributes") or {}
    if (
        observation.get("brand") != product.get("brand")
        or observation.get("concentration") != attrs.get("concentration")
        or type(observation.get("volume_ml")) is not int
        or str(observation.get("volume_ml")) != str(attrs.get("volume_ml"))
    ):
        raise ValueError("brand_concentration_or_volume_mismatch")

    gtin = observation.get("ean")
    if not valid_gtin(gtin):
        raise ValueError("source_ean_missing_or_invalid")
    expected = [
        row
        for row in mappings.get("mappings", [])
        if row.get("product_id") == offer.get("product_id")
        and merchant_key(row.get("merchant")) == merchant_key(offer.get("merchant_id"))
        and row.get("merchant_product_id") == offer.get("merchant_product_id")
        and row.get("mapping_status") == "verified_current_variant"
    ]
    if len(expected) != 1 or gtin != (expected[0].get("gtin") or expected[0].get("ean")):
        raise ValueError("source_ean_or_merchant_sku_mapping_unverified")
