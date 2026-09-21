from copy import deepcopy

from scripts.validate_dufynd_catalog_expansion_wave import (
    DEFAULT_WAVE,
    load_json,
    valid_gtin,
    validate_research_details,
    validate_wave,
)


def test_valid_wave_rejects_existing_products_and_accepts_new_variant() -> None:
    catalog = {
        "products": [
            {
                "product_id": "SC-LIVE-1",
                "category": "fragrance",
                "in_stock": True,
            }
        ]
    }
    staging = {"products": [{"product_id": "SC-STAGED-1"}]}

    wave = {
        "candidates": [
            {
                "product_id": "SC-NEW-1",
                "brand": "Brand",
                "name": "Name",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "variant_status": "verified_retail_variant",
                "evidence": [{"url": "https://example.test/product"}],
            }
        ]
    }
    assert validate_wave(wave, catalog, staging) == []

    wave["candidates"].append(
        {
            "product_id": "SC-LIVE-1",
            "brand": "Brand",
            "name": "Existing",
            "concentration": "Eau de Parfum",
            "volume_ml": 100,
            "variant_status": "verified_retail_variant",
            "evidence": [{"url": "https://example.test/existing"}],
        }
    )

    errors = validate_wave(wave, catalog, staging)
    assert "candidate_2:already_live:SC-LIVE-1" in errors


def test_enriched_research_cannot_contain_active_affiliate_url() -> None:
    catalog = {"products": []}
    staging = {"products": []}
    wave = {
        "enrichment": {"total_enriched": 1},
        "candidates": [
            {
                "product_id": "SC-RESEARCH-1",
                "brand": "Brand",
                "name": "Research",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "variant_status": "verified_retail_variant",
                "evidence": [{"url": "https://example.test/product"}],
                "product_data": {
                    "source_url": "https://example.test/official",
                    "source_kind": "official_brand",
                },
                "research_merchant_evidence": [
                    {
                        "merchant": "merchant",
                        "url": "https://example.test/merchant",
                        "affiliate_state": "application_pending",
                        "affiliate_url": "https://example.test/tracked",
                    }
                ],
            }
        ],
    }

    errors = validate_wave(wave, catalog, staging)
    assert "candidate_1:merchant_1:affiliate_url_not_allowed_in_research" in errors


def test_enrichment_total_must_match_enriched_candidates() -> None:
    catalog = {"products": []}
    staging = {"products": []}
    wave = {
        "enrichment": {"total_enriched": 2},
        "candidates": [
            {
                "product_id": "SC-RESEARCH-1",
                "brand": "Brand",
                "name": "Research",
                "concentration": "Eau de Parfum",
                "volume_ml": 100,
                "variant_status": "verified_retail_variant",
                "evidence": [{"url": "https://example.test/product"}],
                "product_data": {
                    "source_url": "https://example.test/official",
                    "source_kind": "official_brand",
                },
                "research_merchant_evidence": [
                    {
                        "merchant": "merchant",
                        "url": "https://example.test/merchant",
                        "affiliate_state": "application_pending",
                    }
                ],
            }
        ],
    }

    errors = validate_wave(wave, catalog, staging)
    assert "enrichment_total_mismatch" in errors


def test_gtin_preserves_leading_zeroes_and_checks_digit() -> None:
    assert valid_gtin("0088300162505")
    assert valid_gtin("088300162505")
    assert valid_gtin("03614223113347")
    for value in (88300162505, "0088300162506", "１２３４５６７０", "", None):
        assert not valid_gtin(value)


def test_research_rejects_wrong_size_concentration_and_unproven_canonical_id() -> None:
    row = deepcopy(load_json(DEFAULT_WAVE)["candidates"][0])
    assert validate_research_details(row, "candidate") == []
    row["identifiers"]["observations"][0]["volume_ml"] = 50
    assert "candidate:identifier_1:variant_mismatch" in validate_research_details(row, "candidate")
    row["identifiers"]["observations"][0]["volume_ml"] = row["volume_ml"]
    row["identifiers"]["observations"][0]["concentration"] = "Eau de Toilette"
    assert "candidate:identifier_1:variant_mismatch" in validate_research_details(row, "candidate")
    row["identifiers"]["canonical_gtin"] = "8411061026342"
    row["validation"]["catalog_ready"] = True
    errors = validate_research_details(row, "candidate")
    assert "candidate:canonical_gtin_not_allowed_in_research" in errors
    assert "candidate:research_must_remain_blocked" in errors


def test_community_rejects_nan_boolean_count_and_missing_source_date() -> None:
    row = deepcopy(load_json(DEFAULT_WAVE)["candidates"][0])
    row["community"].update(rating_10=float("nan"), rating_count=True, checked_at="bad")
    errors = validate_research_details(row, "candidate")
    assert "candidate:invalid_rating_10" in errors
    assert "candidate:invalid_rating_count" in errors
    assert "candidate:invalid_community_checked_at" in errors


def test_research_summary_detects_missing_identifier_observation() -> None:
    wave = deepcopy(load_json(DEFAULT_WAVE))
    wave["candidates"][0]["identifiers"]["observations"] = []
    errors = validate_wave(wave, {"products": []}, {"products": []})
    assert "candidate_1:missing_identifier_evidence" in errors
    assert "enrichment_identifier_source_evidence_count_mismatch" in errors
