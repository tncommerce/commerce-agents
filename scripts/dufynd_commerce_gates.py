"""Shared, offline DUFYND merchant and exact-variant release gates.

No network access, no link generation, no product or image publication.
Only previously approved canonical affiliate URLs may be reused.
"""

from __future__ import annotations

from examples.retail.api.runtime_offer_snapshots import approved_affiliate_route, merchant_key
from scripts.validate_dufynd_catalog_expansion_wave import valid_gtin


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
