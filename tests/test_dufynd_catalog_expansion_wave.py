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
