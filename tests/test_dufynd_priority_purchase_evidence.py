"""The reviewed purchase paths must stay bound to their exact merchant variants."""

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from retail.api.merchant_offers import MerchantOfferStore, offer_clickout_target

DATA = Path("examples/retail/data")


def test_reviewed_paths_resolve_to_exact_current_variants():
    evidence = json.loads((DATA / "dufynd_priority_purchase_evidence_20261009.json").read_text())
    store = MerchantOfferStore(DATA / "merchant_offers.json")
    current_rows = {
        row["offer_id"]: row
        for row in json.loads((DATA / "merchant_offers.json").read_text())["offers"]
    }
    catalog = json.loads((DATA / "catalog.json").read_text())
    catalog_ids = {row["product_id"] for row in catalog["products"]}
    for row in evidence["products"]:
        assert row["product_id"] in catalog_ids
        historical_check = datetime.fromisoformat(row["checked_at"].replace("Z", "+00:00"))
        current_check = datetime.fromisoformat(
            current_rows[row["offer_id"]]["last_updated_at"].replace("Z", "+00:00")
        )
        # The historical identity evidence stays immutable. A later verified
        # refresh must not be evaluated as a future-dated offer on its old clock.
        assert current_check >= historical_check
        offer = store.eligible_offer(row["offer_id"], now=current_check)
        assert offer is not None
        assert offer.merchant_product_id == row["merchant_product_id"]
        assert offer.price == row["regular_price_eur"]
        target = urlsplit(offer_clickout_target(offer))
        assert target.hostname == "www.jdoqocy.com"
        assert target.path == "/click-101884613-12260695"
        assert parse_qs(target.query)["url"] == [row["product_url"]]
        assert "/p-" in row["product_url"]
        assert row["remaining_purchase_blocker"] is None
