"""No-network safeguards for bounded unpublished Awin photo discovery."""
from __future__ import annotations

import hashlib
import unittest

from scripts.export_dufynd_awin_staging_photo_leads import build_staging_review


class StagingPhotoDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.secret = "test-only-unique-publisher-credential-20261027"
        self.source = b"synthetic-source-bytes-not-a-real-feed"
        self.meta = {
            "source": "awin_product_feed_list",
            "advertiser_id": "31081",
            "feed_id": "91379",
            "joined": True,
            "membership_status": "active",
            "downloaded": True,
            "checked_at": "2026-10-27T07:00:00Z",
            "download_sha256": hashlib.sha256(self.source).hexdigest(),
            "downloaded_bytes": len(self.source),
        }
        self.staging = {
            "status": "staging_only_not_loaded_by_live_storefront",
            "products": [
                {
                    "product_id": "SC-STAGE-00",
                    "brand": "Burberry",
                    "name": "Goddess",
                    "concentration": "Eau de Parfum",
                    "volume_ml": 100,
                }
            ] + [
                {
                    "product_id": f"SC-STAGE-{i:02d}",
                    "brand": "SyntheticBrand",
                    "name": f"Nevermatch{i}",
                    "concentration": "Eau de Parfum",
                    "volume_ml": 100,
                }
                for i in range(1, 21)
            ],
        }
        self.published = {"products": [{"product_id": "SC-EXISTING"}]}
        self.row = {
            "merchant_product_id": "123456",
            "product_name": "Burberry Goddess EdP Nat. Spray",
            "aw_product_id": "999000",
            "merchant_deep_link": "https://www.topparfuemerie.de/burberry-goddess-edp-nat-spray",
            "aw_deep_link": "https://www.awin1.com/pclick.php?p=999000&a=3099222&m=31081",
            "merchant_image_url": "https://www.topparfuemerie.de/media/catalog/product/1/2/123456_123456_051.png",
            "search_price": "93.95",
        }

    def run_review(self, rows=None, meta=None, staging=None, published=None, secret=None):
        return build_staging_review(
            rows if rows is not None else [self.row],
            meta if meta is not None else self.meta,
            self.source,
            secret if secret is not None else self.secret,
            staging if staging is not None else self.staging,
            published if published is not None else self.published,
        )

    def test_source_lead_never_approves_variant_offer_or_image(self):
        r = self.run_review()
        self.assertEqual(r["staging_profiles_reviewed"], 20)
        self.assertEqual(r["name_matched_sku_count"], 1)
        self.assertEqual(r["status"], "UNPUBLISHED_STAGING_DISCOVERY_ONLY_NOT_APPROVED")
        self.assertEqual(r["rows"][0]["candidate_staging_product_ids"], ["SC-STAGE-00"])
        self.assertFalse(r["rows"][0]["exact_concentration_and_size_verified"])
        self.assertFalse(r["rows"][0]["offer_activated"])
        self.assertFalse(r["rows"][0]["image_publication_allowed"])
        self.assertEqual(r["approved_new_images"], 0)
        self.assertEqual(r["approved_new_offers"], 0)
        self.assertNotIn("search_price", r["rows"][0]["fields"])
        self.assertNotIn(self.secret, str(r))

    def test_incorrect_or_unapproved_feed_is_rejected(self):
        for altered in (
            {**self.meta, "feed_id": "91378"},
            {**self.meta, "membership_status": "pending"},
            {**self.meta, "download_sha256": "f" * 64},
        ):
            with self.subTest(metadata=altered):
                with self.assertRaises(ValueError):
                    self.run_review(meta=altered)
        with self.assertRaises(ValueError):
            self.run_review(secret="")

    def test_too_many_names_remain_unapproved_holds(self):
        rows = [{**self.row, "merchant_product_id": str(i)} for i in range(100001, 100013)]
        r = self.run_review(rows=rows)
        self.assertEqual(r["name_matched_sku_count"], 0)
        self.assertEqual(r["scope"][0]["status"], "AMBIGUOUS_NAME_HOLD")
        self.assertEqual(r["rows"], [])

    def test_published_profile_excluded_from_staging_batch(self):
        p = {"products": [{"product_id": "SC-STAGE-00"}]}
        r = self.run_review(published=p)
        self.assertEqual(r["staging_profiles_reviewed"], 20)
        self.assertEqual(r["name_matched_sku_count"], 0)
        self.assertFalse(any(x["product_id"] == "SC-STAGE-00" for x in r["scope"]))


if __name__ == "__main__":
    unittest.main()
