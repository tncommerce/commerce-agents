from scripts.report_dufynd_partner_overlap import build_partner_overlap_report


def test_partner_overlap_separates_live_and_staged_products() -> None:
    report = build_partner_overlap_report(
        catalog={
            "products": [
                {
                    "product_id": "SC-LIVE-1",
                    "category": "fragrance",
                    "in_stock": True,
                    "brand": "Live Brand",
                    "name": "Live Scent",
                    "image_url": "/products/live.webp",
                }
            ]
        },
        staging={
            "products": [
                {
                    "product_id": "SC-STAGED-1",
                    "brand": "Stage Brand",
                    "name": "Stage Scent",
                    "media": {
                        "image_url": None,
                        "image_status": "pending",
                    },
                }
            ]
        },
        mappings_payload={
            "mappings": [
                {
                    "product_id": "SC-LIVE-1",
                    "merchant": "perfumetrader",
                    "merchant_product_id": "111",
                    "ean": "1111111111111",
                    "gtin": "1111111111111",
                },
                {
                    "product_id": "SC-STAGED-1",
                    "merchant": "perfumetrader",
                    "merchant_product_id": "222",
                    "ean": "2222222222222",
                    "gtin": "2222222222222",
                },
            ]
        },
        offers_payload={
            "offers": [
                {
                    "product_id": "SC-LIVE-1",
                    "merchant_id": "perfumetrader",
                    "affiliate_url": "https://example.test/tracked",
                }
            ]
        },
        partners_payload={
            "partners": [
                {
                    "merchant_id": "perfumetrader",
                    "merchant_name": "Perfumetrader",
                    "status": "active",
                    "affiliate_url": "https://example.test/general",
                }
            ]
        },
        releases=[
            {
                "release_id": "DUFYND-RELEASE-01",
                "product_ids": ["SC-STAGED-1"],
            }
        ],
        merchant="perfumetrader",
    )

    assert report["partner_status"] == "active"
    assert report["partner_tracking_url_configured"] is True
    assert report["mapped_product_count"] == 2
    assert report["mapped_live_product_count"] == 1
    assert report["mapped_staged_product_count"] == 1
    assert report["product_affiliate_offer_count"] == 1

    live_row = next(
        row for row in report["rows"] if row["product_id"] == "SC-LIVE-1"
    )
    assert live_row["catalog_state"] == "live"
    assert live_row["blockers"] == []

    staged_row = next(
        row for row in report["rows"] if row["product_id"] == "SC-STAGED-1"
    )
    assert staged_row["catalog_state"] == "staged"
    assert staged_row["release_ids"] == ["DUFYND-RELEASE-01"]
    assert staged_row["blockers"] == [
        "approved_image_missing",
        "product_affiliate_offer_missing",
    ]
