"""Validate this captured offer candidate offline; never apply or contact a merchant."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from examples.retail.api.merchant_offers import MerchantOffer, customer_offer_payload
from examples.retail.api.runtime_offer_snapshots import (
    IDENTITY_FIELDS,
    apply_runtime_snapshot,
)
from scripts.prepare_dufynd_runtime_offer_batch import batch_digest, prepare_batch

ROOT = Path(__file__).resolve().parents[2]
PACKET = Path(__file__).resolve().parent
DATA = ROOT / "examples/retail/data"


def main() -> None:
    source_bytes = (PACKET / "source-observation.json").read_bytes()
    source = json.loads(source_bytes)
    evidence = json.loads((PACKET / "batch-input.json").read_text())
    canonical_rows = json.loads((DATA / "merchant_offers.json").read_text())["offers"]
    candidate = evidence["offers"][0]
    canonical = next(row for row in canonical_rows if row["offer_id"] == candidate["offer_id"])
    at = datetime.fromisoformat(source["observed_at"].replace("Z", "+00:00"))
    expires = at + timedelta(hours=72)
    checks = []

    def require(condition: bool, name: str) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    require(
        hashlib.sha256(source_bytes).hexdigest()
        == candidate["evidence"]["source_observation_sha256"],
        "input binds the exact normalized source observation",
    )
    selected = source["jsonld_selected_offer"]
    require(
        selected["sku"] == source["selected_variant"]["jsonld_sku"] == "YSLLBRW_AEDP10"
        and selected["url"] == canonical["product_url"].removeprefix("https://www.notino.de")
        and source["visible_merchant_product_id"] == canonical["merchant_product_id"] == "VZR11010",
        "visible merchant code and selected JSON-LD offer bind the approved exact URL",
    )
    require(
        source["selected_variant"]["volume_ml"] == candidate["volume_ml"] == 90
        and source["selected_variant"]["gtin13"] == candidate["ean"] == "3614272648425"
        and source["selected_variant"]["presentation"] == "refillable_bottle_not_refill",
        "90 ml refillable bottle identity matches the freshly captured GTIN",
    )
    require(
        selected["price"] == candidate["price"] == 130
        and selected["priceCurrency"] == "EUR"
        and selected["availability"] == "https://schema.org/InStock"
        and candidate["in_stock"] is True
        and source["selected_variant"]["shipping_cost_eur"] == candidate["shipping_cost"] == 0
        and source["selected_variant"]["shipping_country"] == "DE",
        "candidate keeps selected 130 EUR offer and observed free German delivery",
    )
    prepared = prepare_batch(canonical_rows, evidence, now=at)
    require(len(prepared) == 1, "existing release gates accept exactly one captured offer")
    row = apply_runtime_snapshot(canonical, prepared[0], now=at)
    require(row is not None, "existing runtime projection accepts the source-bound candidate")
    require(
        all(row[field] == canonical.get(field) for field in IDENTITY_FIELDS),
        "runtime projection preserves every approved identity and affiliate destination field",
    )
    payload = customer_offer_payload(MerchantOffer.model_validate(row))
    require(
        payload["price"] == payload["total_price"] == 130 and payload["shipping_cost"] == 0,
        "actual customer payload presents 130 EUR total without substituting the cheaper 100 ml variant",
    )
    require(
        apply_runtime_snapshot(canonical, prepared[0], now=expires) is not None
        and apply_runtime_snapshot(canonical, prepared[0], now=expires + timedelta(microseconds=1))
        is None,
        "candidate obeys the exact existing 72 hour freshness boundary",
    )
    try:
        prepare_batch(canonical_rows, evidence, now=expires + timedelta(microseconds=1))
    except ValueError as error:
        require(
            str(error) == "expired_or_future_source", "import rejects this candidate after expiry"
        )
    else:
        raise AssertionError("expired candidate accepted")
    for field, replacement in (("volume_ml", 100), ("ean", "3614273941136")):
        wrong = copy.deepcopy(evidence)
        wrong["offers"][0][field] = replacement
        try:
            prepare_batch(canonical_rows, wrong, now=at)
        except ValueError:
            checks.append(f"import rejects neighboring variant substitution via {field}")
        else:
            raise AssertionError(f"wrong {field} accepted")

    print(
        json.dumps(
            {
                "status": "PASS_OFFLINE_CANDIDATE",
                "base_commit": "a4f79726bc55fa579909e2f4b7955b361e474814",
                "batch_id": evidence["batch_id"],
                "batch_sha256": batch_digest(prepared, batch_id=evidence["batch_id"]),
                "observation_at": at.isoformat(),
                "expires_at": expires.isoformat(),
                "checks": checks,
                "network_requests": 0,
                "runtime_writes": 0,
                "affiliate_clickouts": 0,
                "analytics_events": 0,
                "live_customer_api_verified_after_apply": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
