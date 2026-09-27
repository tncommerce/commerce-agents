"""Protect committed DUFYND merchant offers from structural data drift."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

OFFERS = Path("examples/retail/data/merchant_offers.json")
SOURCE = Path("examples/retail/data/scentai_products.json")
STAGING = Path("examples/retail/data/scentai_catalog_staging.json")


def _offers() -> list[dict]:
    return json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]


def _valid_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname)


def test_offer_ids_are_unique_and_products_are_known() -> None:
    offers = _offers()
    live = json.loads(SOURCE.read_text(encoding="utf-8"))["products"]
    staged = json.loads(STAGING.read_text(encoding="utf-8"))["products"]
    known_ids = {row["product_id"] for row in live} | {row["product_id"] for row in staged}

    offer_ids = [row["offer_id"] for row in offers]
    assert len(offer_ids) == len(set(offer_ids))

    unknown = sorted({row["product_id"] for row in offers if row["product_id"] not in known_ids})
    assert not unknown, f"merchant offers reference unknown products: {unknown}"


def test_offer_commerce_fields_are_valid() -> None:
    for offer in _offers():
        offer_id = offer["offer_id"]

        assert float(offer["price"]) > 0, offer_id
        assert str(offer["currency"]).strip().upper() == "EUR", offer_id
        assert _valid_https_url(str(offer["product_url"])), offer_id

        affiliate_url = str(offer.get("affiliate_url") or "").strip()
        if affiliate_url:
            assert _valid_https_url(affiliate_url), offer_id


def test_offer_freshness_timestamps_are_parseable() -> None:
    for offer in _offers():
        value = str(offer["last_updated_at"]).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)

        assert parsed.tzinfo is not None, offer["offer_id"]


def test_release02_pure_musc_offer_is_exact_and_untracked() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_release02_pure_musc_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "sephora-pure-musc-edp-100")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"]
    assert offer["product_url"] == evidence["product_url"]
    assert offer["variant_label"] == "100 ml · Eau de Parfum"
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "sephora"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_release03_additional_offers_match_observed_variants() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_release03_additional_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offers = {row["product_id"]: row for row in _offers()}

    assert len(evidence["products"]) == 3
    assert evidence["rights_or_affiliate_impact"] == {
        "image_rights_granted": False,
        "affiliate_tracking_verified": False,
        "final_image_approval_granted": False,
    }
    for product in evidence["products"]:
        offer = offers[product["product_id"]]
        identity = product["identity"]
        assert offer["merchant_product_id"] == product["merchant_product_id"]
        assert offer["product_url"] == product["product_url"]
        assert offer["variant_label"] == (
            f"{identity['volume_ml']} ml · {identity['concentration']}"
        )
        assert offer["last_updated_at"] == evidence["observed_at"]
        assert offer["affiliate_url"] is None
        assert offer["commission_rate"] is None
        assert any(
            row["product_id"] == product["product_id"]
            and row["merchant"] == "parfumdreams"
            and row["merchant_product_id"] == product["merchant_product_id"]
            and row["gtin"] == identity["gtin"]
            for row in mappings
        )


def test_release03_ombre_leather_offer_keeps_edp_100ml_variant() -> None:
    evidence = json.loads(
        Path(
            "examples/retail/data/dufynd_release03_ombre_leather_purchase_evidence.json"
        ).read_text(encoding="utf-8")
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "mueller-ombre-leather-edp-100")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"]
    assert offer["product_url"] == evidence["product_url"]
    assert offer["variant_label"] == "100 ml · Eau de Parfum"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "mueller"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_release02_chloe_offer_is_refillable_bottle_not_refill() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_release02_chloe_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "sephora-chloe-edp-100")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"]
    assert offer["product_url"] == evidence["product_url"]
    assert offer["variant_label"] == "100 ml · Eau de Parfum · nachfüllbarer Flakon"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "sephora"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_le_male_elixir_offer_selects_parfum_125ml_variant() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_jpg_le_male_elixir_125_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(
        row for row in _offers() if row["offer_id"] == "douglas-jpg-le-male-elixir-parfum-125"
    )

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"]
    assert offer["product_url"].endswith("?variant=1092117")
    assert offer["variant_label"] == "125 ml · Parfum"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "douglas"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_good_girl_offer_selects_original_edp_80ml_not_refill() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_good_girl_80_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "mueller-good-girl-edp-80")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"] == "2070740"
    assert offer["product_url"].endswith("?itemId=2070740")
    assert offer["variant_label"] == "80 ml · Eau de Parfum"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "mueller"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_baccarat_rouge_offer_selects_edp_70ml_not_extrait() -> None:
    evidence = json.loads(
        Path(
            "examples/retail/data/dufynd_baccarat_rouge_540_edp_70_purchase_evidence.json"
        ).read_text(encoding="utf-8")
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "douglas-baccarat-rouge-540-edp-70")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"]
    assert offer["product_url"].endswith("?variant=922888")
    assert offer["variant_label"] == "70 ml · Eau de Parfum"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "douglas"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_armani_si_offer_selects_refillable_edp_bottle_not_refill() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_armani_si_edp_100_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "mueller-armani-si-edp-100")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"] == "689615"
    assert offer["product_url"].endswith("?itemId=689615")
    assert offer["variant_label"] == "100 ml · Eau de Parfum · nachfüllbarer Flakon"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "mueller"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )


def test_rabanne_1_million_offer_selects_edt_100ml_not_parfum() -> None:
    evidence = json.loads(
        Path("examples/retail/data/dufynd_rabanne_1_million_edt_100_purchase_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    mappings = json.loads(
        Path("examples/retail/data/merchant_product_mappings.json").read_text(encoding="utf-8")
    )["mappings"]
    offer = next(row for row in _offers() if row["offer_id"] == "mueller-rabanne-1-million-edt-100")

    assert offer["product_id"] == evidence["product_id"]
    assert offer["merchant_product_id"] == evidence["merchant_product_id"] == "241929"
    assert offer["product_url"] == evidence["product_url"]
    assert offer["variant_label"] == "100 ml · Eau de Toilette"
    assert offer["last_updated_at"] == evidence["observed_at"]
    assert offer["affiliate_url"] is None
    assert offer["commission_rate"] is None
    assert evidence["identity"]["gtin"] == "3349666007921"
    assert evidence["rights_or_affiliate_impact"]["image_rights_granted"] is False
    assert any(
        row["product_id"] == offer["product_id"]
        and row["merchant"] == "mueller"
        and row["merchant_product_id"] == offer["merchant_product_id"]
        and row["gtin"] == evidence["identity"]["gtin"]
        for row in mappings
    )
