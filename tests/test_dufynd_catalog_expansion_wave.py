from scripts.validate_dufynd_catalog_expansion_wave import validate_wave


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
